from flask import Flask, render_template, request, send_file, after_this_request
import numpy as np
import plotly.graph_objs as go
import plotly.offline as pyo
import os
import uuid

# PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)

datos_pdf = []
kpis_global = {}
params_global = {}

# ================= INTERPRETACIÓN =================
def generar_interpretacion(T0, Ta, k, t_estab, error_avg):
    tipo = "enfriamiento" if T0 > Ta else "calentamiento"

    if k < 0.03:
        velocidad = "lenta"
    elif k < 0.08:
        velocidad = "moderada"
    else:
        velocidad = "rápida"

    return f"""
    El sistema presenta un proceso de {tipo} con una velocidad {velocidad}, 
    determinado por un coeficiente k = {k}.

    Se estima que alcanza estabilidad térmica en aproximadamente {t_estab} minutos.

    El error promedio del método de Euler es de {error_avg} °C, lo que indica 
    una aproximación numérica confiable.

    En general, valores altos de k representan una transferencia de calor más eficiente,
    mientras que valores bajos indican procesos más lentos.
    """

# ================= RECOMENDACIONES =================
def generar_recomendaciones(T0, Ta, k, t_estab, error_avg):
    recomendaciones = []

    if T0 > 70:
        recomendaciones.append("El servidor inicia con temperatura elevada. Se recomienda mejorar la ventilación o usar enfriamiento adicional.")

    if k < 0.03:
        recomendaciones.append("El sistema enfría lentamente. Se sugiere aumentar la eficiencia térmica.")
    elif k > 0.08:
        recomendaciones.append("El sistema presenta un enfriamiento eficiente.")

    if isinstance(t_estab, (int, float)) and t_estab > 30:
        recomendaciones.append("El sistema tarda mucho en enfriarse. Se recomienda mejorar la ventilación o reducir la carga térmica.")

    if not recomendaciones:
        recomendaciones.append("El sistema funciona correctamente bajo las condiciones actuales.")

    return recomendaciones

# ================= RUTA PRINCIPAL =================
@app.route('/', methods=['GET', 'POST'])
def index():
    global datos_pdf, kpis_global, params_global

    grafica_html = None
    grafica_error_html = None
    tabla = []
    error_msg = None
    kpis = None
    interpretacion = None
    recomendaciones = None

    if request.method == 'POST':
        try:
            T0 = float(request.form['T0'])
            Ta = float(request.form['Ta'])
            k = float(request.form['k'])
            dt = float(request.form['dt'])

            if k <= 0 or dt <= 0:
                error_msg = "Los valores deben ser mayores a 0."
            else:
                t = np.arange(0, 50 + dt, dt)

                T_analitica = Ta + (T0 - Ta) * np.exp(-k * t)

                T_euler = [T0]
                for i in range(1, len(t)):
                    T_new = T_euler[-1] + dt * (-k * (T_euler[-1] - Ta))
                    T_euler.append(T_new)

                T_euler = np.array(T_euler)
                error = np.abs(T_analitica - T_euler)

                error_max = np.max(error)
                error_avg = np.mean(error)

                umbral = Ta + 0.01 * (T0 - Ta)
                indices_estables = np.where(
                    T_analitica <= umbral if T0 > Ta else T_analitica >= umbral
                )[0]

                t_estab = round(t[indices_estables[0]], 2) if len(indices_estables) > 0 else "No alcanza"

                kpis = {
                    'error_max': round(error_max, 5),
                    'error_avg': round(error_avg, 5),
                    't_estabilizacion': t_estab
                }

                kpis_global = kpis
                params_global = {'T0': T0, 'Ta': Ta, 'k': k}

                tabla = list(zip(t, T_analitica, T_euler, error))
                datos_pdf = tabla

                interpretacion = generar_interpretacion(T0, Ta, k, t_estab, error_avg)
                recomendaciones = generar_recomendaciones(T0, Ta, k, t_estab, error_avg)

                frames = [
                    go.Frame(data=[
                        go.Scatter(x=t[:i+1], y=T_analitica[:i+1]),
                        go.Scatter(x=t[:i+1], y=T_euler[:i+1])
                    ])
                    for i in range(0, len(t), 2)
                ]

                fig1 = go.Figure(
                    data=[
                        go.Scatter(
                            x=t,  # 🔥 ya NO vacío
                            y=T_analitica,
                            name='Temp. Real',
                            line=dict(color='#3b82f6', width=3)
                        ),
                        go.Scatter(
                            x=t,
                            y=T_euler,
                            name='Aprox. Euler',
                            line=dict(color='#22c55e', width=3)
                        )
                    ],
                    layout=go.Layout(
                        template="plotly_dark",
                        dragmode='pan',

                        xaxis=dict(title="Tiempo (min)", gridcolor="#334155"),
                        yaxis=dict(title="Temperatura (°C)", gridcolor="#334155"),

                        height=500,
                        margin=dict(l=50, r=30, t=80, b=120),

                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1
                        ),

                        updatemenus=[{
                            "type": "buttons",
                            "direction": "left",
                            "x": 0.5,
                            "y": -0.2,
                            "xanchor": "center",
                            "yanchor": "top",
                            "showactive": False,
                            "buttons": [
                                {
                                    "label": "▶ Reproducir",
                                    "method": "animate",
                                    "args": [None, {
                                        "frame": {"duration": 50, "redraw": True},
                                        "fromcurrent": True
                                    }]
                                },
                                {
                                    "label": "⏸ Pausar",
                                    "method": "animate",
                                    "args": [[None], {
                                        "frame": {"duration": 0, "redraw": False},
                                        "mode": "immediate"
                                    }]
                                }
                            ]
                        }]
                    ),
                    frames=frames
                )

                grafica_html = pyo.plot(fig1, output_type='div')

                fig2 = go.Figure(go.Scatter(x=t, y=error))
                fig2.update_layout(template="plotly_dark", height=300)
                grafica_error_html = pyo.plot(fig2, output_type='div')

        except Exception as e:
            error_msg = str(e)

    return render_template(
        'index.html',
        grafica_html=grafica_html,
        grafica_error_html=grafica_error_html,
        tabla=tabla,
        error=error_msg,
        kpis=kpis,
        interpretacion=interpretacion,
        recomendaciones=recomendaciones
    )

# ================= PDF =================
@app.route('/pdf')
def generar_pdf():
    global datos_pdf, kpis_global, params_global

    if not datos_pdf:
        return "Sin datos", 400

    filename = f"reporte_{uuid.uuid4().hex}.pdf"

    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()

    contenido = []

    contenido.append(Paragraph("REPORTE DE SIMULACIÓN TÉRMICA", styles['Title']))
    contenido.append(Spacer(1, 15))

    contenido.append(Paragraph("Análisis del comportamiento térmico", styles['Normal']))
    contenido.append(Spacer(1, 20))

    kpi_text = f"""
    <b>Resultados:</b><br/>
    Error promedio: {kpis_global['error_avg']} °C<br/>
    Error máximo: {kpis_global['error_max']} °C<br/>
    Tiempo de estabilización: {kpis_global['t_estabilizacion']} min
    """
    contenido.append(Paragraph(kpi_text, styles['Normal']))
    contenido.append(Spacer(1, 20))

    interp = generar_interpretacion(
        params_global['T0'],
        params_global['Ta'],
        params_global['k'],
        kpis_global['t_estabilizacion'],
        kpis_global['error_avg']
    )

    recs = generar_recomendaciones(
        params_global['T0'],
        params_global['Ta'],
        params_global['k'],
        kpis_global['t_estabilizacion'],
        kpis_global['error_avg']
    )

    contenido.append(Paragraph("Interpretación del modelo", styles['Heading2']))
    contenido.append(Spacer(1, 10))
    contenido.append(Paragraph(interp, styles['Normal']))
    contenido.append(Spacer(1, 20))

    contenido.append(Paragraph("Recomendaciones", styles['Heading2']))
    contenido.append(Spacer(1, 10))

    for r in recs:
        contenido.append(Paragraph(f"• {r}", styles['Normal']))
        contenido.append(Spacer(1, 5))

    contenido.append(Spacer(1, 20))

    data = [["Tiempo", "Real", "Euler", "Error"]] + [
        [f"{f[0]:.2f}", f"{f[1]:.2f}", f"{f[2]:.2f}", f"{f[3]:.4f}"]
        for f in datos_pdf
    ]

    tabla_pdf = Table(data, repeatRows=1)
    tabla_pdf.setStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.darkblue),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey)
    ])

    contenido.append(Paragraph("Datos de simulación", styles['Heading2']))
    contenido.append(Spacer(1, 10))
    contenido.append(tabla_pdf)

    doc.build(contenido)

    @after_this_request
    def remove_file(response):
        try:
            os.remove(filename)
        except:
            pass
        return response

    return send_file(filename, as_attachment=True, download_name="reporte.pdf")

if __name__ == '__main__':
    app.run(debug=True)