"""Create an original short setup fixture; full-song writing is an agent task."""
import argparse
from pathlib import Path
from musiclib.model import save_json,validate

def example():
    p={'schema':'music-production/v1','title':'Four-bar setup study','version':'1.0','clock':{'bars':4,'meter':[4,4],'tempo':[[0,108],[8,112]],'tail_seconds':3},'sections':[{'id':'question','start_bar':0,'bars':2,'intent':'Short opening phrase'},{'id':'answer','start_bar':2,'bars':2,'intent':'Cadential answer'}],'tracks':[],'mix':{'target_lufs':-18,'peak_ceiling_db':-1.6,'max_limit_db':.8,'room_seconds':.7},'decisions':['Functional fixture only; not a demonstration of a complete song.']}
    def add(ident,role,program,engine='soundfont',drums=False,level=-27):
        t={'id':ident,'name':ident,'role':role,'engine':engine,'drums':drums,'program':program,'bank':0,'range':[0,127],'notes':[],'performance':{'notes':{},'cc':[]},'mix':{'level_dbfs':level,'level_mode':'peak' if drums else 'active_rms','pan':0,'highpass':35 if role=='bass' else 130,'lowpass':14000,'reverb_db':-19 if not drums else None,'delay_db':-24 if engine=='additive' else None,'eq':[],'automation':[]}}
        p['tracks'].append(t);return t
    def n(t,on,dur,pitch,velocity=76,gate=1,timing=0):
        ident=t['id']+'_n'+str(len(t['notes']));t['notes'].append({'id':ident,'on':on,'duration':dur,'pitch':pitch,'phrase':'setup','articulation':'rise' if t['engine']=='noise' else 'normal'});t['performance']['notes'][ident]={'velocity':velocity,'gate':gate,'timing_ms':timing}
    piano=add('piano','harmony',0,level=-29)
    bass=add('bass','bass',33,level=-27)
    lead=add('lead','melody',80,'additive',level=-25)
    drums=add('drums','drums',0,drums=True,level=-20)
    fx=add('fx','effect',0,'noise',level=-38)
    for bar,chord in enumerate(([60,64,67],[62,65,69],[60,64,69],[59,62,67])):
        for i,pitch in enumerate(chord):n(piano,bar*4+i*.5,.85,pitch,62+i*3,1.05)
        piano['performance']['cc'] += [[bar*4,64,0],[bar*4+.07,64,100]]
        n(bass,bar*4,3.5,[36,38,33,31][bar],74,.96)
        for beat,pitch,vel in [(0,36,87),(1,38,88),(2.5,36,70),(3,38,90)]:n(drums,bar*4+beat,.12,pitch,vel,.8,4 if pitch==38 else 0)
    for on,dur,pitch in [(0,1.5,72),(1.5,.5,74),(2,1.5,76),(4,1.5,77),(6,1.5,74),(8,1,76),(9,.5,74),(9.5,.5,72),(10,1.5,69),(12,1,71),(13,.5,74),(13.5,.5,71),(14,1.7,72)]:n(lead,on,dur,pitch,82,1.02)
    n(fx,6,1.75,60,62,.8,20)
    validate(p);return p

if __name__=='__main__':
    from musiclib import files
    files.escape_unprintable()
    a=argparse.ArgumentParser();a.add_argument('--output',type=Path,required=True);args=a.parse_args()
    files.fresh(args.output)
    save_json(args.output,example(),new=True);print(args.output)
