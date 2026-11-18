import sys, warnings; warnings.filterwarnings("ignore"); sys.path.insert(0,".")
import numpy as np
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.impute import KNNImputer
from sklearn.preprocessing import StandardScaler
from ml.data import load_heart, load_diabetes
def mk():
    rf=Pipeline([("i",KNNImputer(n_neighbors=7)),("m",RandomForestClassifier(500,max_depth=8,min_samples_leaf=2,random_state=1))])
    ann=Pipeline([("i",KNNImputer(n_neighbors=7)),("s",StandardScaler()),("m",MLPClassifier((32,16),alpha=0.1,max_iter=800,random_state=1))])
    return VotingClassifier([("rf",rf),("ann",ann)],voting="soft",weights=[.7,.3])
def report(name,X,y):
    accs=[]
    P=np.zeros((len(y),len(set(y))))
    for rep in range(3):
        P+=cross_val_predict(mk(),X,y,cv=StratifiedKFold(5,shuffle=True,random_state=rep),method="predict_proba",n_jobs=2)
    P/=3; pred=P.argmax(1); conf=P.max(1)
    print(name,"overall acc",round((pred==y.values).mean(),4))
    for t in [0.6,0.7,0.75,0.8,0.85,0.9]:
        m=conf>=t
        if m.sum()>20: print(f"  conf>={t}: coverage {m.mean():.2f} acc {(pred[m]==y.values[m]).mean():.3f}")
X,y,s=load_heart(); report("heart-binary",X,(y>0).astype(int))
report("heart-5class",X,y)
Xd,yd=load_diabetes(); report("diabetes",Xd,yd)
