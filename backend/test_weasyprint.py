from weasyprint import HTML
import io
import traceback

try:
    html_content = "<html><body><h1>Test</h1></body></html>"
    pdf_file = io.BytesIO()
    print("Iniciando generación de PDF de prueba...")
    HTML(string=html_content).write_pdf(pdf_file)
    print("PDF de prueba generado con éxito.")
except Exception as e:
    print(f"Error en PDF de prueba: {e}")
    traceback.print_exc()
