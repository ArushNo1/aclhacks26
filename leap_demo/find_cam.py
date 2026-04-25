import cv2
for i in range(8):
    cap = cv2.VideoCapture(i, cv2.CAP_V4L2)                                                      
    if not cap.isOpened(): continue
    ok, f = cap.read()                                                                           
    if ok and f is not None:                              
        h, w = f.shape[:2]                                                                       
        print(f"video{i}: {w}x{h} mean={f.mean():.1f}")   
    cap.release()
