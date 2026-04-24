from flask import Flask, render_template, request, send_file
import numpy as np
import plotly.graph_objs as go
import plotly.offline as pyo
import os
import uuid
from flask import after_this_request

# PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)

datos_pdf = []
kpis_global = {}

@app.route('/', methods=['GET', 'POST'])
def index():
    global datos_pdf, kpis_global
    grafica_html = None
    grafica_error_html = None
    tabla = []
    error_msg = None
    kpis = None

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

                # Modelo analítico
                T_analitica = Ta + (T0 - Ta) * np.exp(-k * t)

                # Método de Euler
                T_euler = [T0]
                for i in range(1, len(t)):
                    T_new = T_euler[-1] + dt * (-k * (T_euler[-1] - Ta))
                    T_euler.append(T_new)

                T_euler = np.array(T_euler)
                error = np.abs(T_analitica - T_euler)

                # KPIs
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
                tabla = list(zip(t, T_analitica, T_euler, error))
                datos_pdf = tabla

                # 🔥 FRAMES PARA ANIMACIÓN
                frames = [
                    go.Frame(data=[
                        go.Scatter(x=t[:i+1], y=T_analitica[:i+1]),
                        go.Scatter(x=t[:i+1], y=T_euler[:i+1])
                    ])
                    for i in range(0, len(t), 2)
                ]

                # 🔥 FIGURA PRINCIPAL MEJORADA
                fig1 = go.Figure(
                    data=[
                        go.Scatter(x=[], y=[], name='Temp. Real', line=dict(color='#3b82f6', width=3)),
                        go.Scatter(x=[], y=[], name='Aprox. Euler', line=dict(color='#22c55e', width=3))
                    ],
                    layout=go.Layout(
                        template="plotly_dark",
                        dragmode='pan',
                        xaxis=dict(title="Tiempo (min)", gridcolor="#334155"),
                        yaxis=dict(title="Temperatura (°C)", gridcolor="#334155"),

                        margin=dict(l=50, r=30, t=60, b=60),

                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1
                        ),

                        # 🔥 BOTONES BIEN POSICIONADOS
                        updatemenus=[{
                            "type": "buttons",
                            "direction": "left",
                            "x": 0.5,
                            "y": -0.2,   # 👈 ahora abajo
                            "xanchor": "center",
                            "yanchor": "top",
                            "pad": {"r": 10, "t": 10},
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

                # 🔥 CONFIG LIMPIA
                grafica_html = pyo.plot(
                    fig1,
                    output_type='div',
                    config={
                        'displayModeBar': True,
                        'displaylogo': False,
                        'responsive': True,
                        'modeBarButtonsToRemove': [
                            'lasso2d',
                            'select2d',
                            'autoScale2d'
                        ]
                    }
                )

                # Gráfica de error
                fig2 = go.Figure(go.Scatter(x=t, y=error, line=dict(color='#ef4444')))
                fig2.update_layout(title="Margen de Error", template="plotly_dark", height=300)

                grafica_error_html = pyo.plot(
                    fig2,
                    output_type='div',
                    config={'displayModeBar': False}
                )

        except Exception as e:
            error_msg = f"Error en los datos: {str(e)}"

    return render_template(
        'index.html',
        grafica_html=grafica_html,
        grafica_error_html=grafica_error_html,
        tabla=tabla,
        error=error_msg,
        kpis=kpis
    )


@app.route('/pdf')
def generar_pdf():
    global datos_pdf, kpis_global

    if not datos_pdf:
        return "Sin datos", 400

    filename = f"reporte_{uuid.uuid4().hex}.pdf"

    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()

    contenido = [
        Paragraph("Reporte de Simulación Térmica", styles['Title'])
    ]

    resumen = f"Error Promedio: {kpis_global['error_avg']}°C | Tiempo: {kpis_global['t_estabilizacion']} min"
    contenido.append(Paragraph(resumen, styles['Normal']))
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

    contenido.append(tabla_pdf)
    doc.build(contenido)

    # 🔥 BORRAR DESPUÉS DE ENVIAR (SOLUCIÓN REAL)
    @after_this_request
    def remove_file(response):
        try:
            os.remove(filename)
        except Exception as e:
            print("Error borrando archivo:", e)
        return response

    return send_file(filename, as_attachment=True, download_name="Reporte.pdf")


if __name__ == '__main__':
    app.run(debug=True)