exec(open('/output/make_boards.py').read().split('index=[]')[0])
centers=[0,109,185,240,268,290,300,306,309,311,313,314,315,315,316,316,261,287,294,295,295,296,296,297,297,297,297,298,298,298,299]
targets=[r for r in rows if r['split']!='train']
locations=[]
for r,c in zip(targets,centers):
    locations.append((r,max(0,c-25),235,50,65))
for r in rows:
    if r['frame']<13400:
        locations.append((r,140,245,50,30))
for start in range(0,len(locations),12):
    sheet=np.full((4*310,3*250,3),245,dtype=np.uint8)
    for i,(r,a,b,w,h) in enumerate(locations[start:start+12]):
        im=cv2.imread(str(source/'dataset'/r['image']))
        crop=cv2.resize(im[b:b+h,a:a+w],None,fx=4,fy=4,interpolation=cv2.INTER_NEAREST)
        x,y=i%3*250,i//3*310
        sheet[y+30:y+30+h*4,x:x+w*4]=crop
        cv2.putText(sheet,f"{r['frame']} x{a} y{b}",(x+2,y+20),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,0,0),1)
        for dy in range(0,h,10):
            cv2.putText(sheet,str(b+dy),(x+201,y+40+dy*4),cv2.FONT_HERSHEY_SIMPLEX,.35,(0,0,0),1)
    cv2.imwrite(str(out/f'localize-{start//12+1:02d}.png'),sheet)
