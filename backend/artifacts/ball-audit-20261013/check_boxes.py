exec(open('/output/make_boards.py').read().split('index=[]')[0])
from review_decisions import decision
selected=[r for r in rows if decision(r['frame'])[0]]
for start in range(0,len(selected),12):
    sheet=np.full((4*180,3*300,3),245,dtype=np.uint8)
    for i,r in enumerate(selected[start:start+12]):
        im=cv2.imread(str(source/'dataset'/r['image']))
        box=decision(r['frame'])[0][0]
        a,b=box[0]-15,box[1]-10
        crop=im[b:b+35,a:a+45].copy()
        cv2.rectangle(crop,(box[0]-a,box[1]-b),(box[2]-a,box[3]-b),(0,255,0),1)
        x,y=i%3*300,i//3*180
        sheet[y+30:y+170,x:x+180]=cv2.resize(crop,None,fx=4,fy=4,interpolation=cv2.INTER_NEAREST)
        cv2.putText(sheet,str(r['frame']),(x+2,y+20),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,0,0),1)
    cv2.imwrite(str(out/f'boxes-{start//12+1:02d}.png'),sheet)
