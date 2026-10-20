"""Unmarked, nearest-neighbour details for manual background-ball review."""
exec(open('/output/make_boards.py').read().split('index=[]')[0])
for start in range(0,len(rows),12):
    chunk=rows[start:start+12]
    sheet=np.full((4*240,3*480,3),245,dtype=np.uint8)
    for i,row in enumerate(chunk):
        frame=cv2.imread(str(source/'dataset'/row['image']))
        # Broad left-wall region; later camera pans need wider context.
        roi=(110,225,230,278) if row['frame']<13400 else (0,245,400,330)
        a,b,c,d=roi
        crop=cv2.resize(frame[b:d,a:c],(480,210),interpolation=cv2.INTER_NEAREST)
        x,y=i%3*480,i//3*240
        sheet[y+30:y+240,x:x+480]=crop
        cv2.putText(sheet,f"{row['frame']} ROI {roi}",(x+4,y+21),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,0,0),1)
    cv2.imwrite(str(out/f'detail-{start//12+1:02d}.png'),sheet)
