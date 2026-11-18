import sys, warnings; warnings.filterwarnings("ignore"); sys.path.insert(0,".")
import numpy as np, pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.ensemble import RandomForestClassifier, VotingClassifier, ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.impute import KNNImputer, SimpleImputer
from sklearn.preprocessing import StandardScaler, FunctionTransformer
from xgboost import XGBClassifier
from ml.data import load_heart
X,y,s=load_heart(); yb=(y>0).astype(int)
def fe(df):
    d=pd.DataFrame(df,columns=X.columns).copy()
    d["hr_reserve"]=d["thalach"]/(220-d["age"])
    d["chol_age"]=d["chol"]/d["age"]
    d["st_hr"]=d["oldpeak"]*d["exang"].fillna(0)
    return d.values
F=lambda: FunctionTransformer(lambda a: fe(a), validate=False)
def P(m,scale=False,eng=False):
    st=[("i",KNNImputer(n_neighbors=7))]
    if eng: st.append(("f",F()))
    if scale: st.append(("s",StandardScaler()))
    st.append(("m",m)); return Pipeline(st)
cands={
 "rf":P(RandomForestClassifier(500,max_depth=8,min_samples_leaf=2,random_state=1)),
 "rf_fe":P(RandomForestClassifier(500,max_depth=8,min_samples_leaf=2,random_state=1),eng=True),
 "xgb":P(XGBClassifier(n_estimators=250,max_depth=3,learning_rate=0.04,subsample=0.8,colsample_bytree=0.8,reg_lambda=3,verbosity=0,random_state=1,n_jobs=1)),
 "xgb_fe":P(XGBClassifier(n_estimators=250,max_depth=3,learning_rate=0.04,subsample=0.8,colsample_bytree=0.8,reg_lambda=3,verbosity=0,random_state=1,n_jobs=1),eng=True),
 "lr_fe":P(LogisticRegression(C=0.3,max_iter=3000),scale=True,eng=True),
 "ann_fe":P(MLPClassifier((32,16),alpha=0.3,max_iter=800,random_state=1),scale=True,eng=True),
}
oof={}
for k,m in cands.items():
    p=np.zeros(len(yb))
    for rep in range(3):
        p+=cross_val_predict(m,X,yb,cv=StratifiedKFold(5,shuffle=True,random_state=rep),method="predict_proba",n_jobs=2)[:,1]
    oof[k]=p/3; print(k,round(((oof[k]>.5)==yb).mean(),4))
import itertools
for combo in [("rf_fe","ann_fe"),("rf_fe","xgb_fe","ann_fe"),("rf_fe","xgb_fe","lr_fe","ann_fe")]:
    p=np.mean([oof[c] for c in combo],0); print(combo,round(((p>.5)==yb).mean(),4))
