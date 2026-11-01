"""Reconstrucción y digitalización de la referencia Anime Socks.

Ejecutar con Python y dependencias de requirements.txt. No sustituye una prueba física.
Las curvas florales fueron reconstruidas mirando la referencia. La caligrafía
se obtiene de sus píxeles, y sus columnas se dirigen mediante ejes revisados.
"""
from pathlib import Path
import sys, argparse, json, math, copy, subprocess, re

parser = argparse.ArgumentParser()
parser.add_argument('--referencia', required=True)
parser.add_argument('--salida', required=True)
parser.add_argument('--vendor')
parser.add_argument('--escala-fisica',type=float,default=1.0)
args = parser.parse_args()
import numpy as np
from PIL import Image
from lxml import etree as ET
if args.vendor:sys.path.append(args.vendor)

def gaussian_filter1d(p,sigma,axis=0,mode='nearest'):
    radius=max(1,int(math.ceil(sigma*3))); weights=np.exp(-np.arange(-radius,radius+1)**2/(2*sigma*sigma));weights/=weights.sum()
    pad=np.pad(p,((radius,radius),(0,0)),mode='wrap' if mode=='wrap' else 'edge')
    return sum(w*pad[j:j+len(p)] for j,w in enumerate(weights))

def approximate_polygon(p,tol):
    p=np.asarray(p)
    if len(p)<3:return p
    a,b=p[0],p[-1];v=b-a
    if np.linalg.norm(v)<1e-8:
        k=len(p)//2;return np.concatenate([approximate_polygon(p[:k+1],tol)[:-1],approximate_polygon(p[k:],tol)])
    t=np.clip((p-a)@v/(v@v),0,1);dist=np.linalg.norm(p-(a+t[:,None]*v),axis=1);k=int(np.argmax(dist))
    if dist[k]<=tol:return np.array([a,b])
    return np.concatenate([approximate_polygon(p[:k+1],tol)[:-1],approximate_polygon(p[k:],tol)])

def polygon_area(p):
    p=np.asarray(p);return .5*float(np.sum(p[:,0]*np.roll(p[:,1],-1)-p[:,1]*np.roll(p[:,0],-1)))

def inside(point,p):
    x,y=point; a=np.asarray(p);b=np.roll(a,-1,axis=0)
    cross=((a[:,1]>y)!=(b[:,1]>y)) & (x<(b[:,0]-a[:,0])*(y-a[:,1])/(b[:,1]-a[:,1]+1e-20)+a[:,0])
    return bool(np.count_nonzero(cross)%2)

def boundaries(m):
    # Ordered pixel boundary edges; no compiled tracing libraries required.
    edges={};h,w=m.shape
    for y,x in zip(*np.where(m)):
        x=int(x);y=int(y)
        if y==0 or not m[y-1,x]:edges.setdefault((x,y),[]).append((x+1,y))
        if x==w-1 or not m[y,x+1]:edges.setdefault((x+1,y),[]).append((x+1,y+1))
        if y==h-1 or not m[y+1,x]:edges.setdefault((x+1,y+1),[]).append((x,y+1))
        if x==0 or not m[y,x-1]:edges.setdefault((x,y+1),[]).append((x,y))
    loops=[]
    while edges:
        start=next(iter(edges));p=[start];cur=start
        for _ in range(20000):
            if cur not in edges:break
            nxt=edges[cur].pop()
            if not edges[cur]:del edges[cur]
            p.append(nxt);cur=nxt
            if cur==start:break
        if len(p)>10:loops.append(np.asarray(p,float)-.5)
    return loops

def map_coordinates(m,coords,**kw):
    y,x=coords;y=np.round(y).astype(int);x=np.round(x).astype(int)
    valid=(y>=0)&(y<m.shape[0])&(x>=0)&(x<m.shape[1]);o=np.zeros(len(y));o[valid]=m[y[valid],x[valid]];return o

OUT=Path(args.salida); OUT.mkdir(parents=True,exist_ok=True)
WORK=OUT/'trabajo'; WORK.mkdir(exist_ok=True)
SVG='http://www.w3.org/2000/svg'; INK='http://www.inkscape.org/namespaces/inkscape'
IS='http://inkstitch.org/namespace'
NS={None:SVG,'inkscape':INK,'inkstitch':IS}
SCALE=150/1057
COLORS={'malva':'#967E88','rosa':'#EDB3B5','rosa_oscuro':'#BF7F85'}
im=np.array(Image.open(args.referencia).convert('RGB'))
if im.shape[:2]!=(1402,1122): raise ValueError('Se requiere la referencia original de 1122 × 1402 px')
mask=(im[:,:,0]<205)&(im[:,:,1]<184)&(im[:,:,2]<194)

def fmt(x): return f'{float(x):.3f}'.rstrip('0').rstrip('.')
def polyline(points,closed=False):
    points=np.array(points); s='M'+','.join(map(fmt,points[0]))
    s+=''.join(' L'+','.join(map(fmt,p)) for p in points[1:])
    return s+(' Z' if closed else '')

def bezier(points, closed=False):
    """Catmull–Rom interpolation of a simplified, smoothed contour."""
    p=np.asarray(points,dtype=float)
    if closed and np.linalg.norm(p[0]-p[-1])<1: p=p[:-1]
    if len(p)<3:return polyline(p,closed)
    s='M'+','.join(map(fmt,p[0])); n=len(p)
    for i in range(n if closed else n-1):
        a=p[(i-1)%n] if closed or i else p[i]
        b=p[i]; c=p[(i+1)%n]; d=p[(i+2)%n] if closed or i+2<n else c
        c1=b+(c-a)/6; c2=c-(d-b)/6
        s+=' C'+' '.join(','.join(map(fmt,v)) for v in (c1,c2,c))
    return s+(' Z' if closed else '')

def trace_box(box,name):
    x0,y0,x1,y1=box; m=np.zeros(mask.shape,dtype=bool);m[y0:y1,x0:x1]=mask[y0:y1,x0:x1]
    yy,xx=np.indices(m.shape)
    if name=='Anime':
        m &= ((yy>620)|(xx>270)) & ((yy<780)|(xx<500))
        m &= ~((xx>615)&(xx<690)&(yy<626))
    paths=[]
    loops=boundaries(m);outers=[p for p in loops if polygon_area(p)>10];holes=[p for p in loops if polygon_area(p)<-5]
    for p in outers:
        if name=='Anime' and p[:,1].max()<630:continue
        parts=[p]+[h for h in holes if inside(h[0],p)]
        ds=[]
        for q in parts:
            q=gaussian_filter1d(q,.8,axis=0,mode='wrap');q=approximate_polygon(q,.65)
            ds.append(bezier(q,True))
        paths.append(' '.join(ds))
    return paths

objects=[]; vector=[]; checks=[]
def add(id,d,color,kind,role,**options):
    objects.append(dict(id=id,d=d,color=color,kind=kind,role=role,options=options))
def art(id,d,color,role,fill=True,opacity=1):
    vector.append(dict(id=id,d=d,color=color,role=role,fill=fill,opacity=opacity))

# Bézier paths reconstructed by hand from the reference, each petal independent.
upper=[
'M205,394 C186,371 145,337 151,310 C152,297 159,288 165,287 C168,267 198,265 205,280 C221,260 240,274 244,286 C252,287 260,307 260,320 C260,348 232,376 211,396 Z',
'M211,396 C228,374 249,344 268,335 C286,322 301,327 310,336 C338,336 342,355 330,366 C348,365 345,385 332,400 C325,413 307,425 291,427 C266,430 238,412 215,405 Z',
'M212,406 C247,409 281,422 291,444 C300,456 296,474 287,477 C290,493 277,500 267,496 C263,514 241,508 230,502 C211,493 202,477 202,457 L204,415 Z',
'M198,407 C174,412 128,433 112,450 C103,461 102,472 109,476 C102,495 116,507 128,494 C127,510 148,512 161,506 C181,497 197,480 200,457 L201,415 Z',
'M198,394 C180,367 154,330 119,331 C107,330 98,336 98,341 C76,342 64,359 80,372 C56,376 64,396 85,410 C78,420 99,431 116,430 C139,428 162,413 195,405 Z']
lower=[
'M918,981 C892,946 861,914 872,885 C873,871 880,875 881,872 C890,849 914,838 932,859 C951,839 973,859 974,877 C989,895 987,916 978,938 C961,957 939,980 923,986 Z',
'M925,986 C953,956 976,937 1005,939 C1022,944 1051,949 1051,959 C1061,969 1054,983 1048,987 C1071,990 1065,1012 1051,1022 C1038,1035 1012,1034 994,1028 C968,1020 943,1009 925,997 Z',
'M924,1000 C959,1008 984,1032 998,1052 C1019,1076 1015,1102 1004,1099 C1005,1116 984,1125 969,1116 C961,1134 941,1120 927,1111 C908,1098 904,1078 905,1056 L916,1005 Z',
'M912,1000 C875,1007 834,1020 819,1040 C804,1057 808,1072 816,1077 C807,1101 824,1110 842,1100 C845,1113 864,1106 876,1100 C901,1092 908,1075 909,1054 L913,1006 Z',
'M911,984 C883,953 852,912 823,915 C806,914 794,918 789,928 C774,936 780,950 792,953 C769,954 779,975 790,985 C794,1000 814,1013 834,1013 C862,1011 892,998 911,991 Z']
def circle(cx,cy,r):
    k=r*.55228475
    return f'M{cx-r},{cy} C{cx-r},{cy-k} {cx-k},{cy-r} {cx},{cy-r} C{cx+k},{cy-r} {cx+r},{cy-k} {cx+r},{cy} C{cx+r},{cy+k} {cx+k},{cy+r} {cx},{cy+r} C{cx-k},{cy+r} {cx-r},{cy+k} {cx-r},{cy} Z'
def sampled(d,step=2):
    tok=re.findall(r'[MCLZ]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?',d); i=0;parts=[];pts=[];cmd=None;current=None;start=None
    while i<len(tok):
        if tok[i] in 'MCLZ':cmd=tok[i];i+=1
        if cmd=='M':
            if pts:parts.append(np.array(pts));pts=[]
            current=np.array(list(map(float,tok[i:i+2])));i+=2;start=current.copy();pts.append(current);cmd='L'
        elif cmd=='L':
            target=np.array(list(map(float,tok[i:i+2])));i+=2
            n=max(2,int(np.linalg.norm(target-current)/step)+1)
            pts.extend(np.linspace(current,target,n)[1:]);current=target
        elif cmd=='C':
            a,b,c=np.array(list(map(float,tok[i:i+6]))).reshape(3,2);i+=6
            n=max(5,int((np.linalg.norm(a-current)+np.linalg.norm(b-a)+np.linalg.norm(c-b))/step)+1)
            for t in np.linspace(0,1,n)[1:]:pts.append((1-t)**3*current+3*(1-t)**2*t*a+3*(1-t)*t*t*b+t**3*c)
            current=c
        elif cmd=='Z':
            if np.linalg.norm(current-start)>.01:pts.append(start)
            current=start;cmd=None
        else:raise ValueError('Comando desconocido en '+d)
    if pts:parts.append(np.array(pts))
    return parts

for name,petals,cx,cy in [('superior',upper,205,401),('inferior',lower,918,991)]:
    for i,d in enumerate(petals):
        id=f'flor_{name}_petalo_{i+1}';art(id,d,'rosa','petalos',opacity=.55)
        # Punch out the center and shrink away from its outline to prevent a dense hub.
        q=sampled(d)[0];v=q-[cx,cy];length=np.linalg.norm(v,axis=1); q=np.array([cx,cy])+v*np.maximum(1,12/np.maximum(length,.01))[:,None]
        centroid=q.mean(axis=0);v=q-centroid;length=np.linalg.norm(v,axis=1);q=centroid+v*(1-1.2/np.maximum(length,1.3))[:,None]
        dd=polyline(approximate_polygon(q,.35),True)
        add(id+'_relleno',dd,'rosa','fill','petalos',spacing=.85,angle=25+i*31)
        # Open outer petal contour excludes the common center junction.
        pts=sampled(d)[0]; dist=np.linalg.norm(pts-[cx,cy],axis=1)
        good=dist>12
        edges=[];start=None
        for k,ok in enumerate(good):
            if ok and start is None:start=k
            if start is not None and (not ok or k==len(good)-1):
                stop=k if not ok else k+1
                if stop-start>4:edges.append(pts[start:stop])
                start=None
        for j,e in enumerate(edges):
            de=bezier(approximate_polygon(e,.55))
            add(id+'_contorno'+str(j),de,'rosa_oscuro','run','contornos',length=2.1)
            art(id+'_contorno'+str(j),de,'rosa_oscuro','contornos',False)
    # Ten stamens instead of reproducing every tiny dot and line at the center.
    for k in range(10):
        a=2*math.pi*k/10+.16; r=38 if k%2 else 49
        inner=np.array([cx,cy])+11*np.array([math.cos(a),math.sin(a)])
        tip=np.array([cx,cy])+r*np.array([math.cos(a),math.sin(a)])
        d=polyline([inner,tip,inner])
        add(f'flor_{name}_estambre_{k+1}',d,'rosa_oscuro','run','estambres',length=2.0)
        art(f'flor_{name}_estambre_{k+1}',polyline([inner,tip]),'rosa_oscuro','estambres',False)
    d=circle(cx,cy,7.5);art(f'flor_{name}_centro',d,'rosa','centros')
    add(f'flor_{name}_centro',d,'rosa','fill','centros',spacing=.5,angle=0)
    add(f'flor_{name}_anillo',circle(cx,cy,8.5),'rosa_oscuro','run','centros',length=1.8)
    art(f'flor_{name}_anillo',circle(cx,cy,8.5),'rosa_oscuro','centros',False)

leaves=[
('superior_izquierda','M85,552 C49,531 55,514 47,461 C60,475 91,480 96,514 C97,530 93,541 85,552 Z','M49,465 C67,492 81,514 85,552'),
('superior_derecha','M111,573 C134,539 160,536 201,547 C178,553 183,573 160,580 C141,587 128,574 111,573 Z','M111,573 C141,561 168,553 201,547'),
('superior_alta','M321,281 C326,263 304,253 327,221 C331,218 331,211 332,209 C342,233 349,247 335,264 C330,272 324,276 321,281 Z','M321,281 C330,254 332,234 332,212'),
('inferior_baja','M754,1120 C732,1090 736,1060 754,1033 C759,1028 759,1022 759,1019 C778,1057 787,1085 774,1103 C771,1114 763,1120 754,1127 Z','M754,1127 C763,1099 764,1056 759,1022'),
('inferior_horizontal','M816,1128 C844,1100 864,1114 883,1129 C898,1142 906,1148 920,1150 C885,1160 852,1169 831,1144 Z','M816,1128 C854,1124 887,1141 920,1150'),
('inferior_derecha','M1005,930 C1033,900 1061,889 1100,899 C1075,915 1084,919 1054,933 C1038,939 1024,935 1005,930 Z','M1005,930 C1040,912 1068,903 1100,899'),
('inferior_alta_derecha','M1043,847 C1057,821 1074,814 1095,812 C1089,827 1086,845 1067,851 C1055,855 1049,852 1043,847 Z','M1043,847 C1061,832 1080,822 1095,812'),
('inferior_alta_izquierda','M1019,858 C988,841 979,821 973,784 C982,795 1009,810 1019,829 C1024,845 1022,854 1019,858 Z','M1019,858 C1009,834 991,807 975,787')]
for name,d,vein in leaves:
    id='hoja_'+name;art(id,d,'malva','hojas',opacity=.6)
    checks.append({'id':id,'area_px2':abs(polygon_area(sampled(d)[0]))})
    add(id+'_relleno',d,'malva','fill','hojas',spacing=.95,angle=40,underlay=False)
    add(id+'_borde',d,'malva','run','hojas',length=2.1)
    add(id+'_nervio',vein,'malva','run','hojas',length=2.3)
    art(id+'_nervio',vein,'malva','nervios',False)

branches=[
('superior_base','M64,668 C62,626 89,567 138,505',2.9),
('superior_hoja_izquierda','M74,604 C86,584 88,566 85,549',2.2),
('superior_hoja_derecha','M78,596 C87,583 99,576 114,572',2.2),
('superior_alta','M260,336 C294,317 341,279 374,239',2.7),
('superior_hoja_alta','M302,308 C320,292 323,281 322,273',1.8),
('superior_capullo_horizontal','M301,309 C321,300 337,295 353,295',1.8),
('inferior_base','M677,1181 C736,1178 791,1125 835,1086',3.0),
('inferior_hoja_baja','M715,1173 C742,1150 756,1135 754,1120',2.0),
('inferior_hoja_horizontal','M750,1150 C778,1132 800,1128 817,1128',1.8),
('inferior_alta','M997,924 C1024,893 1045,848 1042,814',2.7),
('inferior_hoja_izquierda','M1014,896 C1023,881 1022,866 1019,857',1.8),
('inferior_hoja_derecha','M1008,930 C1017,930 1028,928 1034,924',1.7),
('inferior_hoja_alta','M1033,860 C1038,851 1042,847 1048,844',1.8)]
for name,d,w in branches:
    add('rama_'+name,d,'malva','run','ramas',length=2.3,bean=1)
    art('rama_'+name,d,'malva','ramas',False)

buds=[
('superior_alto','M371,239 C370,216 390,177 422,180 C429,178 435,181 433,189 C436,212 406,237 385,242 Z','M370,244 C369,231 371,221 377,214 C375,225 379,230 379,234 C391,222 395,223 401,221 C392,234 386,238 382,240 C395,235 399,235 403,234 C391,245 380,247 370,244 Z','M379,234 C398,215 420,196 431,184'),
('superior_horizontal','M354,294 C376,267 402,263 426,279 C432,283 436,289 432,292 C441,299 422,310 410,313 C388,320 369,309 354,301 Z','M350,297 C357,289 364,285 373,283 C367,289 362,291 361,293 C372,291 376,293 379,296 C372,299 366,298 362,299 C368,303 371,306 375,309 C364,306 356,302 350,297 Z','M365,297 C390,288 414,289 432,293'),
('inferior_alto','M1038,811 C1021,793 1015,768 1024,746 C1026,737 1034,730 1041,733 C1048,723 1052,729 1057,727 C1066,740 1071,759 1069,778 C1066,797 1055,810 1044,814 Z','M1040,823 C1031,811 1028,802 1028,791 C1035,798 1037,805 1038,809 C1037,797 1040,790 1043,786 C1048,794 1047,803 1046,809 C1054,804 1059,798 1064,791 C1061,807 1052,816 1040,823 Z','M1043,806 C1042,779 1048,752 1055,733')]
for name,d,calyx,vein in buds:
    art('capullo_'+name,d,'rosa','capullos',opacity=.6)
    art('caliz_'+name,calyx,'malva','calices')
    add('capullo_'+name,d,'rosa','fill','capullos',spacing=.75,angle=75)
    add('capullo_'+name+'_borde',d,'rosa_oscuro','run','capullos',length=2.1)
    add('capullo_'+name+'_detalle',vein,'rosa_oscuro','run','capullos',length=2.3)
    add('caliz_'+name,calyx,'malva','fill','calices',spacing=.5,angle=65)

# Preserve the real outline of the typography instead of substituting a font.
for name,box in [('Anime',(104,426,1022,817)),('SOCKS',(327,828,784,899)),('corazon_i',(624,571,684,625)),('corazon_inferior',(529,928,589,984))]:
    if name=='corazon_inferior':
        m2=mask.copy();mask=(im[:,:,0]<253)&(im[:,:,1]<222)&(im[:,:,2]<229)
    ds=trace_box(box,name)
    if name=='corazon_inferior':mask=m2
    for k,d in enumerate(ds):
        art(name+'_'+str(k),d,'rosa' if name=='corazon_inferior' else 'malva','tipografia' if name in ['Anime','SOCKS'] else 'corazones')
    if name.startswith('corazon'):
        d=' '.join(ds)
        add(name,d,'rosa' if name=='corazon_inferior' else 'malva','fill','corazones',spacing=.45,angle=45)

# Ejes caligráficos revisados; las anchuras provienen de la referencia a lo
# largo de la normal. Los topes evitan interpretar cruces como trazos anchos.
axes=[
('A_lazo_ascenso','M459,638 C353,630 245,623 177,651 C127,672 109,704 116,739 C126,776 162,776 193,754 C246,717 313,623 365,561 C417,499 459,452 489,437',14),
('A_descenso','M488,439 C486,465 457,530 432,596 C411,650 392,708 384,751 C378,782 381,814 406,805',32),
('n','M495,644 C487,665 468,711 458,736 C484,698 516,651 535,650 C559,651 530,699 527,725 C519,773 579,729 608,700',25),
('i','M637,650 C626,672 607,709 607,730 C602,776 657,738 689,697',25),
('m','M715,650 L680,742 C705,708 737,655 754,656 C779,650 751,706 743,733 C767,698 798,655 817,656 C842,651 811,704 806,725 C792,778 847,730 878,708',25),
('e','M901,701 C920,694 944,680 948,661 C951,639 924,649 910,664 C888,687 878,714 885,734 C899,775 970,731 1016,681',23),
('SOCKS_S_1','M368,842 C354,829 338,837 338,848 C338,860 368,857 368,875 C368,890 349,892 337,881',11),
('SOCKS_O','M453,837 C425,837 425,886 453,886 C485,886 485,837 453,837',11),
('SOCKS_C','M579,843 C546,820 523,871 550,885 C560,891 571,886 579,882',11),
('SOCKS_K_vertical','M641,838 L641,890',11),
('SOCKS_K_diagonales','M678,838 L644,867 L678,889',11),
('SOCKS_S_2','M770,843 C756,831 741,838 741,849 C741,861 771,860 771,878 C771,893 752,893 740,883',11)]

def rails_from_reference(d,cap):
    c=sampled(d,step=3.5)[0]
    tangent=np.gradient(c,axis=0);norm=np.linalg.norm(tangent,axis=1);tangent/=norm[:,None]
    normal=np.column_stack([-tangent[:,1],tangent[:,0]])
    offsets=np.linspace(-cap,cap,round(cap*4)+1)
    left=[];right=[];miss=0
    for pt,nn in zip(c,normal):
        samples=pt+offsets[:,None]*nn
        val=map_coordinates(mask.astype(float),[samples[:,1],samples[:,0]],order=1,mode='constant')>.5
        spans=[];start=None
        for j,v in enumerate(val):
            if v and start is None:start=j
            if start is not None and (not v or j==len(val)-1):
                end=j if not v else j+1;spans.append((offsets[start],offsets[end-1]));start=None
        if spans:
            lo,hi=min(spans,key=lambda s:abs((s[0]+s[1])/2))
            if hi-lo>cap:
                mid=np.clip((lo+hi)/2,-2,2);lo=mid-cap/2;hi=mid+cap/2
            if min(abs(lo),abs(hi))>8 and not(lo<=0<=hi):miss+=1;lo,hi=-cap/3,cap/3
            if hi-lo<2:lo-=.7;hi+=.7
        else:miss+=1;lo,hi=-cap/3,cap/3
        left.append(pt+lo*nn);right.append(pt+hi*nn)
    l=gaussian_filter1d(np.array(left),.7,axis=0,mode='nearest')
    r=gaussian_filter1d(np.array(right),.7,axis=0,mode='nearest')
    widths=np.linalg.norm(l-r,axis=1)*SCALE
    return l,r,miss,widths

for name,d,cap in axes:
    l,r,miss,w=rails_from_reference(d,cap)
    c=(l+r)/2; types=np.where(w<.86,1,0)
    # Remove small alternating classifications; narrow terminals use triple run.
    for j in range(2,len(types)-2):
        types[j]=int(np.median(types[j-2:j+3]))
    if name.startswith('SOCKS'):types[:]=0
    if name=='A_lazo_ascenso':
        skip=((c[:,1]>624)&(c[:,1]<646)&(c[:,0]>414)&(c[:,0]<435))
        skip|=((c[:,1]>620)&(c[:,1]<646)&(c[:,0]>297)&(c[:,0]<311)&(np.arange(len(c))<len(c)/2))
        types[skip]=2
    sections=[];start=0
    for j in range(1,len(types)+1):
        if j==len(types) or types[j]!=types[start]:
            sections.append((start,j,types[start]));start=j
    for part,(start,end,kind) in enumerate(sections):
        if kind==2 or end-start<3:continue
        ll=l[start:end];rr=r[start:end];cc=c[start:end]
        if kind==1:
            add(f'triple_{name}_{part}',bezier(cc),'malva','run','tipografia',length=1.8,bean=1)
            continue
        # Node method: both rails have the same number of cubic segments.
        # Do not introduce guide intersections at tight loops or terminals.
        satin=bezier(ll)+' '+bezier(rr)
        add(f'satin_{name}_{part}',satin,'malva','satin','tipografia',center=float(np.median(w[start:end]))>1.25)
    checks.append({'id':name,'muestras_sin_mascara':miss,'muestras':len(w),'ancho_min_mm':float(w.min()),'ancho_mediano_mm':float(np.median(w)),'ancho_max_mm':float(w.max())})

# The pale photographic disk is omitted. The optional circle is a single run.
circle_d='M1012,679 C1012,420 804,211 549,212 C295,212 87,422 88,680 C88,943 295,1157 549,1156 C806,1156 1014,941 1012,679 Z'
art('circulo_opcional',circle_d,'rosa','circulo',False,opacity=.35)
add('circulo_fino',circle_d,'rosa','run','circulo',length=2.5)

def root():
    e=ET.Element('{'+SVG+'}svg',nsmap=NS,width=fmt(150*args.escala_fisica)+'mm',height=fmt(1006*SCALE*args.escala_fisica)+'mm',viewBox='45 178 1057 1006',version='1.1')
    title=ET.SubElement(e,'{'+SVG+'}title');title.text='Anime Socks · 150 mm · gabardina · Janome MC 550E'
    return e
def layer(e,label,id):
    g=ET.SubElement(e,'{'+SVG+'}g',id=id);g.set('{'+INK+'}groupmode','layer');g.set('{'+INK+'}label',label);return g
def write(e,file):ET.ElementTree(e).write(str(OUT/file),encoding='UTF-8',xml_declaration=True,pretty_print=True)
v=root(); vl={}
for o in vector:
    role=o['role']
    if role not in vl:vl[role]=layer(v,role,'vector_'+role)
    style=f"fill:{COLORS[o['color']]};stroke:none;fill-rule:evenodd" if o['fill'] else f"fill:none;stroke:{COLORS[o['color']]};stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round"
    p=ET.SubElement(vl[role],'{'+SVG+'}path',id=o['id'],d=o['d'],style=style,opacity=str(o['opacity']))
vl['circulo'].set('style','display:none')
write(v,'Anime_Socks_Vector.svg')

def embroidery(optimized,circle=False):
    e=root();meta=ET.SubElement(e,'{'+SVG+'}metadata')
    ET.SubElement(meta,'{'+IS+'}inkstitch_svg_version').text='3'
    ET.SubElement(meta,'{'+IS+'}collapse_len_mm').text='1.2'
    ET.SubElement(meta,'{'+IS+'}min_stitch_len_mm').text='.3'
    selected=[copy.deepcopy(o) for o in objects if circle or o['role']!='circulo']
    if optimized:
        # Greedy routing per thread color. A leaf outline follows its fill;
        # flower centers follow all petals. Satin directions remain controlled.
        selected=[];current=np.array([372.,239.]);done=set()
        for color in COLORS:
            pending=[copy.deepcopy(o) for o in objects if o['color']==color and (circle or o['role']!='circulo')]
            while pending:
                candidates=[]
                for o in pending:
                    if o['role']=='hojas' and o['kind']=='run':
                        dep=o['id'].rsplit('_',1)[0]+'_relleno'
                        if dep not in done:continue
                    if o['role']=='centros' and o['kind']=='fill' and any(q['role']=='petalos' for q in pending):continue
                    parts=sampled(o['d'],8)
                    if o['kind']=='satin':begin=(parts[0][0]+parts[1][0])/2;end=(parts[0][-1]+parts[1][-1])/2
                    else:begin=parts[0][0];end=parts[-1][-1]
                    if o['kind']=='fill':cost=min(np.linalg.norm(current-p,axis=1).min() for p in parts)
                    else:cost=np.linalg.norm(current-begin)
                    rev=o['kind']=='run' and np.linalg.norm(current-end)<cost
                    if rev:cost=np.linalg.norm(current-end)
                    candidates.append((cost,o,begin,end,rev,parts))
                if not candidates:raise ValueError('Ciclo en dependencias de objetos')
                _,o,begin,end,rev,parts=min(candidates,key=lambda a:a[0])
                if rev:
                    o['d']=' '.join(bezier(p[::-1]) for p in parts[::-1]);begin,end=end,begin
                o['begin']=begin;o['end']=end
                selected.append(o);pending.remove(o);done.add(o['id']);current=end
    groups={}
    for i,o in enumerate(selected):
        if optimized:key=o['color']
        else:key=str(i)
        if key not in groups:groups[key]=layer(e,o['color'],f'bloque_{key}')
        p=ET.SubElement(groups[key],'{'+SVG+'}path',id=o['id'],d=o['d'])
        p.set('{'+INK+'}label',o['id'])
        opt=o['options'];par={}
        if o['kind']=='fill':
            style=f"fill:{COLORS[o['color']]};stroke:none;fill-rule:evenodd"
            par={'row_spacing_mm':opt['spacing'],'angle':opt.get('angle',0),'max_stitch_length_mm':2.5,'fill_underlay':False,'pull_compensation_mm':.2}
        elif o['kind']=='satin':
            style=f"fill:none;stroke:{COLORS[o['color']]};stroke-width:1"
            par={'satin_column':True,'zigzag_spacing_mm':.43,'pull_compensation_mm':.2,'center_walk_underlay':opt.get('center',False),'contour_underlay':False,'zigzag_underlay':False,'max_stitch_length_mm':5,'short_stitch_distance_mm':.35,'min_stitch_length_mm':.3,'start_at_nearest_point':False,'end_at_nearest_point':False}
        else:
            style=f"fill:none;stroke:{COLORS[o['color']]};stroke-width:1.6;stroke-dasharray:3,1"
            par={'stroke_method':'running_stitch','running_stitch_length_mm':opt.get('length',2.3),'running_stitch_tolerance_mm':.12,'bean_stitch_repeats':opt.get('bean',0),'repeats':1}
        # Do not leave visible long travel stitches between disjoint objects.
        # The optimization pass will remove redundant trims between close parts.
        do_trim=True
        if optimized and i+1<len(selected):
            nxt=selected[i+1]
            if nxt['color']==o['color'] and np.linalg.norm(o['end']-nxt['begin'])*SCALE*args.escala_fisica<=2.0:do_trim=False
        par['trim_after']=do_trim
        p.set('style',style)
        for k,val in par.items():p.set('{'+IS+'}'+k,str(val))
    return e

write(embroidery(False),'trabajo/Anime_Socks_Inicial.svg')
write(embroidery(True),'Anime_Socks_InkStitch.svg')
write(embroidery(True,True),'trabajo/Anime_Socks_Con_Circulo.svg')
(WORK/'Geometria.json').write_text(json.dumps({'objetos':len(objects),'componentes_vector':len(vector),'comprobaciones':checks},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'objetos':len(objects),'componentes_vector':len(vector),'salida':str(OUT),'controles':checks[-12:]},ensure_ascii=False))
