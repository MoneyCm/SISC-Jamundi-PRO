"""Create the first shared executive brief from a saved public-data snapshot.
No notifications are sent. Proposed actions always require institutional validation.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import urllib.request

import fitz
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'output/pdf'
OUT.mkdir(parents=True, exist_ok=True)
URL = ('http://localhost:5173/api/analitica/public/dashboard?min_location_count=3'
       '&include_map=false&period_mode=year_to_date&comparison=same_period_previous_year')
with urllib.request.urlopen(URL, timeout=30) as response:
    raw = json.load(response)
data = {k: raw[k] for k in ('metadata', 'kpis', 'conductas')}
# Retain only non-personal source metadata in the supporting snapshot.
data['metadata'].pop('last_ingestion', None)
data['retrieved_at'] = datetime.now(ZoneInfo('America/Bogota')).isoformat()
(OUT / 'parte_ejecutivo_sisc_fuente.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
by_code = {item['code']: item for item in data['conductas']}
total = data['kpis']; vehicle = by_code['HURTO_VEHICULOS']; homicide = by_code['HOMICIDIO']; injuries = by_code['LESIONES']
meta = data['metadata']

def n(value):
    return f'{int(value):,}'.replace(',', '.')

def pct(value):
    return f'{value:+.1f}'.replace('.', ',') + ' %'

def date_label(value):
    months = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic']
    dt = datetime.fromisoformat(value[:10])
    return f'{dt.day:02d} {months[dt.month-1]} {dt.year}'

for name, filename in [('Segoe','segoeui.ttf'),('SegoeBold','segoeuib.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(Path('C:/Windows/Fonts') / filename)))
pdfmetrics.registerFontFamily('Segoe', normal='Segoe', bold='SegoeBold', italic='Segoe', boldItalic='SegoeBold')
W,H=595.28,841.89
INK='#111D38'; BLUE='#281FD0'; MUTED='#526079'; LINE='#DDE3EC'; BG='#F3F5FA'
pdf = OUT / 'parte_ejecutivo_sisc.pdf'
c=canvas.Canvas(str(pdf),pagesize=(W,H))
c.setTitle('Parte Ejecutivo SISC | Jamundí | Para validación')
c.setAuthor('SISC Jamundí - propuesta para revisión institucional')

def rect(x,y,w,h,color,r=0):
    c.setFillColor(HexColor(color))
    if r: c.roundRect(x,H-y-h,w,h,r,fill=1,stroke=0)
    else: c.rect(x,H-y-h,w,h,fill=1,stroke=0)

def text(x,y,value,size=11,color=INK,bold=False):
    c.setFillColor(HexColor(color));c.setFont('SegoeBold' if bold else 'Segoe',size)
    c.drawString(x,H-y-size,value)

def para(x,y,value,width=519,size=11,color=INK,bold=False,leading=None):
    style=ParagraphStyle('p',fontName='SegoeBold' if bold else 'Segoe',fontSize=size,leading=leading or size*1.4,textColor=HexColor(color))
    p=Paragraph(value,style); _,height=p.wrap(width,H)
    p.drawOn(c,x,H-y-height)
    return height

def section(y,num,title):
    text(38,y,num,10,BLUE,True);text(63,y-2,title,13,INK,True)

rect(0,0,W,H,'#FFFFFF')
rect(0,0,W,160,INK)
rect(0,0,7,160,'#FFD52A')
text(38,24,'ALCALDÍA DE JAMUNDÍ  /  SISC',10,'#CBD5E8',True)
text(38,47,'Parte ejecutivo',29,'#FFFFFF',True)
text(38,85,'Seguridad y convivencia',14,'#FFFFFF')
rect(38,120,166,22,'#FFD52A',3)
text(47,125,'BORRADOR PARA VALIDACIÓN',8.5,INK,True)
text(224,125,'EDICIÓN  '+date_label(data['retrieved_at']).upper(),9,'#DCE4F4',True)
rect(38,173,519,47,BG,4)
text(50,181,f'Datos: {date_label(meta["period_start"])} al {date_label(meta["period_end"])}',11,INK,True)
text(50,199,f'Comparación: {date_label(meta["comparison_start"])} al {date_label(meta["comparison_end"])}',9.5,MUTED)

section(236,'01','Qué cambió')
tiles=[('CASOS ÚNICOS',n(total['total_hechos']),pct(total['variation_pct']),f'Antes: {n(total["previous_total"])}',BLUE),
       ('HURTO DE VEHÍCULOS¹',n(vehicle['value']),pct(vehicle['variation_pct']),f'Antes: {n(vehicle["previous_value"])}','#B34B14'),
       ('HOMICIDIOS',n(homicide['value']),pct(homicide['variation_pct']),f'Antes: {n(homicide["previous_value"])}',INK)]
for i,(label,value,change,previous,color) in enumerate(tiles):
    x=38+i*177
    rect(x,260,165,98,BG,4)
    text(x+12,271,label,8.6,MUTED,True)
    text(x+12,288,value,28,color,True)
    text(x+91,299,change,12,color,True)
    text(x+12,332,previous,10,MUTED)
text(38,365,'¹ Incluye vehículos y motocicletas. Variaciones frente al mismo periodo de 2025.',8.5,MUTED)

section(391,'02','Qué requiere atención')
para(38,416,f'<b>{n(vehicle["difference"])} hurtos de vehículos y motocicletas más.</b> El aumento contrasta con la reducción del total de casos. Conviene revisar su distribución territorial y temporal antes de priorizar acciones.',size=11.4)

rect(38,481,519,107,'#F0EDFF',4)
section(494,'03','Decisión propuesta al equipo')
para(51,519,'Acordar una revisión conjunta de este aumento y llevar una propuesta sustentada al próximo espacio de coordinación.',width=490,size=11.4,bold=True)
text(51,560,'Por definir: responsable y fecha. Recursos: sin solicitud sustentada.',10,MUTED)

section(607,'04','Seguimiento de compromisos')
para(38,632,'No hay expedientes registrados en el módulo consultado. <b>Validar con las actas</b> y completar responsable, plazo, avance y evidencia. Esto no significa que no existan compromisos fuera del sistema.',size=10.7)

section(693,'05','Resultado observado')
para(38,718,f'<b>Lesiones personales: {n(injuries["value"])} frente a {n(injuries["previous_value"])} ({pct(injuries["variation_pct"])}).</b> La disminución es un dato registrado; no demuestra por sí sola el efecto de una intervención.',size=10.7)

rect(38,775,519,1,LINE)
para(38,784,'Fuente: sábana SIEDCO / Policía Nacional, base consolidada del SISC local. Cifras agregadas; no se suman fuentes ni se publican datos personales. Edición inicial con acumulado anual, no balance semanal.',width=519,size=8.3,color=MUTED,leading=11)
text(38,821,'Acceso al SISC: sisc-frontend.onrender.com',8.5,BLUE,True)
c.linkURL('https://sisc-frontend.onrender.com', (38,H-834,300,H-819),relative=0)
c.showPage(); c.save()
doc=fitz.open(pdf)
assert len(doc)==1
page=doc[0]
png=OUT/'parte_ejecutivo_sisc_whatsapp.png'
page.get_pixmap(matrix=fitz.Matrix(2.2,2.2),alpha=False).save(png)
assert all(n(v) in page.get_text() for v in [total['total_hechos'],vehicle['value'],homicide['value'],injuries['value']])
print(json.dumps({'pdf':str(pdf),'image':str(png),'pages':len(doc),'cutoff':meta['latest_event_date']},ensure_ascii=True))
