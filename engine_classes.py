import xgboost as xgb
import lightgbm as lgb
from sklearn.model_selection import cross_val_predict, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import log_loss
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
import pandas as pd
import numpy as np
import sklearn as _sklearn
import datetime as dt

_SKLEARN_GE_14 = tuple(int(x) for x in _sklearn.__version__.split(".")[:2]) >= (1, 4)
USE_GPU = False
EXCLUDE_COLS = {"game_id","date","date_str","home_team","away_team",
                "home_score","away_score","home_win","total","season",
                "over_5_5","over_6_5","_w"}

DIVISIONS = {
    "Atlantic":  ["BOS","BUF","DET","FLA","MTL","OTT","TBL","TOR"],
    "Metro":     ["CAR","CBJ","NJD","NYI","NYR","PHI","PIT","WSH"],
    "Central":   ["ARI","CHI","COL","DAL","MIN","NSH","STL","WPG"],
    "Pacific":   ["ANA","CGY","EDM","LAK","SEA","SJS","VAN","VGK"],
}
TEAM_DIV = {t: d for d, teams in DIVISIONS.items() for t in teams}

try:
    from catboost import CatBoostClassifier
    _HAS_CAT = True
except Exception:
    _HAS_CAT = False

try:
    import optuna
    _HAS_OPTUNA = True
except Exception:
    _HAS_OPTUNA = False

def _feat_cols(df: pd.DataFrame) -> list:
    return [c for c in df.columns if c not in EXCLUDE_COLS
            and pd.api.types.is_numeric_dtype(df[c])]

class NHLStack:
    def __init__(self, n_cv: int = 5, hpo: bool = True):
        self.n_cv = n_cv
        self.hpo = hpo and _HAS_OPTUNA
        self.scaler = StandardScaler()
        self.bases = []
        self.meta = None
        self.cal = None
        self.fc = None

    def fit(self, df: pd.DataFrame):
        self.fc = _feat_cols(df)
        X = df[self.fc].fillna(0).values
        y = df["home_win"].values
        Xs = self.scaler.fit_transform(X)
        cv = StratifiedKFold(n_splits=self.n_cv, shuffle=True, random_state=42)

        cfgs = [
            ("xgb", xgb.XGBClassifier(n_estimators=400, max_depth=4, learning_rate=0.04, random_state=42, n_jobs=-1, verbosity=0)),
            ("lgb", lgb.LGBMClassifier(n_estimators=400, max_depth=4, learning_rate=0.04, random_state=42, n_jobs=-1, verbose=-1)),
            ("lr",  LogisticRegression(C=0.1, max_iter=500, random_state=42)),
        ]
        
        oof_preds = np.zeros((len(X), len(cfgs)))
        for j, (name, model) in enumerate(cfgs):
            oof = cross_val_predict(model, Xs, y, cv=cv, method="predict_proba")[:,1]
            oof_preds[:, j] = oof
            model.fit(Xs, y)
            self.bases.append((name, model))

        meta_m = lgb.LGBMClassifier(n_estimators=200, max_depth=3, learning_rate=0.03, random_state=42, verbose=-1)
        meta_m.fit(oof_preds, y)
        self.meta = meta_m

        self.cal = CalibratedClassifierCV(meta_m, cv="prefit", method="sigmoid")
        self.cal.fit(oof_preds, y)

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        X  = df[self.fc].fillna(0).values
        Xs = self.scaler.transform(X)
        base_preds = np.column_stack([
            m.predict_proba(Xs)[:,1] for _, m in self.bases
        ])
        return self.cal.predict_proba(base_preds)[:,1]

class NHLElo:
    DEFAULT = 1500.0
    
    def __init__(self, hfa: float = 50.0, regress: float = 0.33):
        self.hfa = hfa
        self.regress = regress
        self.ratings = {}

    def get_rating(self, team: str, sit: str = "overall") -> float:
        return self.ratings.get(team, {}).get(sit, self.DEFAULT)

    def build_from_df(self, df: pd.DataFrame):
        self.ratings = {}
        # Simple backpass to establish live overall and sit ratings
        for r in df.sort_values('Date').itertuples():
            h, a = r.Home, r.Away
            hw = 1 if r.Actual_Winner == h else 0
            
            h_curr = self.get_rating(h, "overall")
            a_curr = self.get_rating(a, "overall")
            
            # Simple Elo Adjustments
            exp_h = 1.0 / (1.0 + 10.0 ** ((a_curr - (h_curr + self.hfa)) / 400.0))
            diff = 24.0 * (hw - exp_h)
            
            self.ratings.setdefault(h, {})["overall"] = h_curr + diff
            self.ratings.setdefault(a, {})["overall"] = a_curr - diff
            
            # Situational maps
            self.ratings.setdefault(h, {})["home"] = self.get_rating(h, "home") + (diff * 0.9)
            self.ratings.setdefault(a, {})["away"] = self.get_rating(a, "away") - (diff * 0.9)

class NHLFormStore:
    def __init__(self):
        self._history = {}

    def build_from_df(self, df: pd.DataFrame):
        self._history = {}
        for r in df.sort_values('Date').itertuples():
            h, a = r.Home, r.Away
            hw = 1 if r.Actual_Winner == h else 0
            
            self._history.setdefault(h, []).append(("W" if hw else "L", h, a))
            self._history.setdefault(a, []).append(("L" if hw else "W", h, a))

    def get_win_rate(self, team: str, n: int) -> float:
        games = self._history.get(team, [])[-n:]
        if not games: return 0.5
        return sum(1 for g in games if g[0] == "W") / len(games)

    def get_streak(self, team: str) -> int:
        games = self._history.get(team, [])
        if not games: return 0
        val = 1 if games[-1][0] == "W" else -1
        count = 0
        for g in reversed(games):
            if (g[0] == "W") == (val > 0): count += 1
            else: break
        return val * count

    def get_h2h(self, h: str, a: str) -> dict:
        h_games = self._history.get(h, [])
        matches = [g for g in h_games if (g[1] == h and g[2] == a) or (g[1] == a and g[2] == h)]
        if not matches:
            return {"h2h_rate": 0.5, "h2h_margin": 0.0, "h2h_total": 0}
        rec = matches[-10:]
        hw = sum(1 for g in rec if (g[0] == "W" and g[1] == h) or (g[0] == "L" and g[1] == a))
        return {
            "h2h_rate": hw / len(rec),
            "h2h_margin": float(hw - (len(rec) - hw)) / len(rec),
            "h2h_total": len(matches)
        }

class NHLStatsTracker:
    def __init__(self):
        self.stats = {}

    def build_from_df(self, df: pd.DataFrame):
        self.stats = {}
        for r in df.itertuples():
            h, a = r.Home, r.Away
            # Fallbacks for raw stats if not fully parsed in past games
            hw = 1 if r.Actual_Winner == h else 0
            self.stats.setdefault(h, []).append((3, 2, hw)) # gf, ga proxies
            self.stats.setdefault(a, []).append((2, 3, 1-hw))

    def get_rolling_metrics(self, team: str, n: int = 10) -> dict:
        rec = self.stats.get(team, [])[-n:]
        if not rec: return {"gf_pct": 0.5, "pdo_proxy": 0.0, "gf_pg": 3.0, "ga_pg": 3.0}
        gf = sum(x[0] for x in rec)
        ga = sum(x[1] for x in rec)
        w  = sum(x[2] for x in rec)
        gf_pct = gf / max((gf + ga), 1)
        return {
            "gf_pct": gf_pct,
            "pdo_proxy": (w / len(rec)) - gf_pct,
            "gf_pg": gf / len(rec),
            "ga_pg": ga / len(rec)
        }

class NHLBetFilter:
    def __init__(self, **overrides):
        self.cfg = {"prob_min": 0.62, "elo_gap_min": 150.0, "big_prob": 0.78, "big_elo_gap": 250.0}