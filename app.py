from flask import Flask, render_template, request, send_file
import numpy as np
import plotly.graph_objs as go
import plotly.offline as pyo
import plotly.io as pio
import os

# PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)

datos_pdf = []

@app.route('/', methods=['GET', 'POST'])
def index():
    global datos_pdf

    grafica_html = None
    grafica_error_html = None
    tabla = []
    error_msg = None

    if request.method == 'POST':
        try:
            T0 = float(request.form['T0'])
            Ta = float(request.form['Ta'])
            k = float(request.form['k'])
            dt = float(request.form['dt'])

            # VALIDACIONES
            if k <= 0:
                error_msg = "k debe ser mayor que 0"
            elif dt <= 0:
                error_msg = "Δt debe ser mayor que 0"
            elif T0 < -273 or Ta < -273:
                error_msg = "Temperaturas no válidas"
            else:
                t = np.arange(0, 50 + dt, dt)
                h = dt

                # ANALÍTICA
                T_analitica = Ta + (T0 - Ta) * np.exp(-k * t)

                # EULER
                T_euler = [T0]
                for i in range(1, len(t)):
                    T_prev = T_euler[-1]
                    T_new = T_prev + h * (-k * (T_prev - Ta))
                    T_euler.append(T_new)

                T_euler = np.array(T_euler)

                # ERROR
                error = np.abs(T_analitica - T_euler)

                tabla = list(zip(t, T_analitica, T_euler, error))
                datos_pdf = tabla

                # 🎬 ANIMACIÓN
                frames = []
                for i in range(len(t)):
                    frames.append(go.Frame(
                        data=[
                            go.Scatter(x=t[:i+1], y=T_analitica[:i+1]),
                            go.Scatter(x=t[:i+1], y=T_euler[:i+1])
                        ]
                    ))

                fig1 = go.Figure(
                    data=[
                        go.Scatter(x=[], y=[], name='Analítica'),
                        go.Scatter(x=[], y=[], name='Euler')
                    ],
                    layout=go.Layout(
                        title="Temperatura vs Tiempo",
                        xaxis=dict(title="Tiempo (minutos)"),
                        yaxis=dict(title="Temperatura (°C)"),
                        updatemenus=[{
                            "type": "buttons",
                            "buttons": [{
                                "label": "▶ Reproducir",
                                "method": "animate",
                                "args": [None, {"frame": {"duration": 100, "redraw": True}}]
                            }]
                        }]
                    ),
                    frames=frames
                )

                grafica_html = pyo.plot(fig1, output_type='div')

                # 🖼️ GUARDAR PARA PDF
                if not os.path.exists("static"):
                    os.makedirs("static")

                ruta_img = "static/grafica.png"
                pio.write_image(fig1, ruta_img)

                # 📉 ERROR
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=t, y=error))
                fig2.update_layout(
                    title="Error absoluto",
                    xaxis_title="Tiempo (minutos)",
                    yaxis_title="Error (°C)"
                )

                grafica_error_html = pyo.plot(fig2, output_type='div')

        except:
            error_msg = "Error en los datos"

    return render_template(
        'index.html',
        grafica_html=grafica_html,
        grafica_error_html=grafica_error_html,
        tabla=tabla,
        error=error_msg
    )


# 📄 PDF
@app.route('/pdf')
def generar_pdf():
    global datos_pdf

    doc = SimpleDocTemplate("reporte.pdf")
    styles = getSampleStyleSheet()

    contenido = []

    # Título
    contenido.append(Paragraph("Reporte de Simulación", styles['Title']))
    contenido.append(Spacer(1, 20))

    # Encabezado
    contenido.append(Paragraph("Tabla de Resultados", styles['Heading2']))
    contenido.append(Spacer(1, 10))

    # Datos de la tabla
    data = [["Tiempo (min)", "Analítica (°C)", "Euler (°C)", "Error (°C)"]]

    for t, a, e, err in datos_pdf:
        data.append([
            f"{t:.2f}",
            f"{a:.2f}",
            f"{e:.2f}",
            f"{err:.4f}"
        ])

    tabla = Table(data)

    # 🎨 ESTILOS PRO
    tabla.setStyle([
        # Encabezado
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),

        # Cuerpo
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),

        # Bordes
        ('GRID', (0, 0), (-1, -1), 1, colors.black),

        # Espaciado
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ])

    contenido.append(tabla)

    doc.build(contenido)

    return send_file("reporte.pdf", as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)