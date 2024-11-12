from flask import Flask, request, render_template_string, redirect, url_for, session
import sqlite3
import pandas as pd
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = 'your_secret_key'  # Necesario para usar sessions

# Asegúrate de que exista el directorio de subida
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Plantilla HTML con CodeMirror y la opción para cargar CSV
HTML_TEMPLATE = '''
    <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Consulta SQLite</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.5/codemirror.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.5/theme/dracula.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.5/codemirror.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.5/mode/sql/sql.min.js"></script>
    <style>
        table {
            width: 100%;
            border-collapse: collapse;
        }
        table, th, td {
            border: 1px solid black;
        }
        th, td {
            padding: 10px;
            text-align: left;
        }
        .CodeMirror {
            height: auto;
        }
        /* Estilo para alinear los formularios de consulta y de inserción */
        .flex-container {
            display: flex;
            gap: 20px; /* Espacio entre los formularios */
        }
        .form-container {
            flex: 1;
        }
    </style>
</head>
<body>
    <h2>Cargar un CSV</h2>
    <form action="{{ url_for('upload_csv') }}" method="post" enctype="multipart/form-data">
        <!-- Input para seleccionar archivo CSV -->
        <input type="file" name="file" accept=".csv" id="csvFile" onchange="enableTableNameInput()">

        <!-- Input para el nombre de la tabla (se muestra cuando se selecciona un archivo) -->
        <label for="tableName">---Nombre de la tabla:</label>
        <input type="text" name="table_name" id="tableName" placeholder="Nombre de la tabla" oninput="toggleSubmitButton()" required>

        <!-- Botón de cargar CSV, deshabilitado por defecto -->
        <input type="submit" value="Cargar CSV" id="submitBtn" disabled>
    </form>

    <h2>Tablas en la base de datos:</h2>
    {% if tables %}
        <table>
            <tbody>
            {% for table in tables %}
                <tr>
                    <td>{{ table[0] }}</td>
                    <td><form action="{{ url_for('truncate_table', table_name=table) }}" method="post" style="display:inline;">
                            <button type="submit" onclick="return confirmTruncate()">Truncar</button>
                        </form>
                    </td>
                    <td><form action="{{ url_for('drop_table', table_name=table) }}" method="post" style="display:inline;">
                            <button type="submit" onclick="return confirmDelete()" style="background-color: red; color: white;">Eliminar</button>
                        </form>
                    </td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
    {% else %}
        <p>No hay tablas disponibles.</p>
    {% endif %}

    <h2>Consulta y Insertar datos</h2>
    <div class="flex-container">
        <!-- Formulario de consulta -->
        <div class="form-container">
            <h3>Consulta la base de datos</h3>
            <form method="post">
                <label for="query">Selects y crear tablas:</label><br><br>
                <textarea id="query" name="query" rows="4" cols="50">{{ query }}</textarea><br><br>
                <input type="submit" value="Ejecutar">
            </form>
        </div>

        <!-- Formulario de inserción -->
        <div class="form-container">
            <h3>Insertar datos</h3>
            <form action="{{ url_for('insert_data') }}" method="post">
                <label for="query">Solo inserts:</label><br><br>
                <textarea id="insert" name="query2" rows="4" cols="50">{{ query2 }}</textarea><br><br>
                <button type="submit">Insertar datos</button>
            </form>
        </div>
    </div>

    <h2>Resultados:</h2>
    {% if results %}
        <table>
            <thead>
                <tr>
                    {% for header in headers %}
                        <th>{{ header }}</th>
                    {% endfor %}
                </tr>
            </thead>
            <tbody>
                {% for row in results %}
                    <tr>
                        {% for item in row %}
                            <td>{{ item }}</td>
                        {% endfor %}
                    </tr>
                {% endfor %}
            </tbody>
        </table>
    {% else %}
        <p>No se encontraron resultados o no se ha ejecutado una consulta.</p>
    {% endif %}

    <script>
        var editor = CodeMirror.fromTextArea(document.getElementById('query'), {
            mode: 'text/x-sql',
            theme: 'dracula',
            lineNumbers: true,
            matchBrackets: true,
            autoCloseBrackets: true,
        });
        
        var editor2 = CodeMirror.fromTextArea(document.getElementById('insert'), {
            mode: 'text/x-sql',
            theme: 'dracula',
            lineNumbers: true,
            matchBrackets: true,
            autoCloseBrackets: true,
        });

        // Función para habilitar el campo de nombre de tabla al seleccionar un archivo
        function enableTableNameInput() {
            var fileInput = document.getElementById('csvFile');
            var tableNameInput = document.getElementById('tableName');

            if (fileInput.files.length > 0) {
                tableNameInput.disabled = false;  // Habilitamos el campo de nombre de tabla
            } else {
                tableNameInput.disabled = true;  // Deshabilitamos el campo de nombre de tabla si no hay archivo
            }

            toggleSubmitButton();  // Verificamos el estado del botón de carga
        }

        // Función para habilitar/deshabilitar el botón de submit según el valor del nombre de la tabla
        function toggleSubmitButton() {
            var tableName = document.getElementById('tableName').value;
            var submitButton = document.getElementById('submitBtn');

            if (tableName.trim() === "") {
                submitButton.disabled = true;  // Deshabilitamos el botón si el campo de nombre de tabla está vacío
            } else {
                submitButton.disabled = false;  // Habilitamos el botón si hay un nombre de tabla
            }
        }

        function confirmTruncate() {
            return confirm("¿Estás seguro de que deseas truncar esta tabla? Esta acción eliminará todos los registros.");
        }

        function confirmDelete() {
            return confirm("¿Estás seguro de que deseas eliminar esta tabla? Esta acción es irreversible.");
        }
    </script>
</body>
</html>
    '''

@app.route('/', methods=['GET', 'POST'])
def index():
    query = ""
    results = []
    headers = []
    tables = []

    # Obtener las tablas de la base de datos
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    try:
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = c.fetchall()
    except Exception as e:
        tables = [["Error: " + str(e)]]
    finally:
        conn.close()

    # Si se ha ejecutado una consulta SQL, mostrar los resultados
    if request.method == 'POST':
        query = request.form['query']

        # Conectar a la base de datos SQLite
        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        try:
            # Ejecutar la consulta SQL
            c.execute(query)
            results = c.fetchall()
            headers = [description[0] for description in c.description]
        except Exception as e:
            results = [["Error: " + str(e)]]
        finally:
            conn.close()

    return render_template_string(HTML_TEMPLATE, query=query, results=results, headers=headers, tables=tables)

@app.route('/insert_data', methods=['GET', 'POST'])
def insert_data():
    if request.method == 'POST':
        insert_query = request.form['query2']  # Aquí se usa 'query2', que corresponde con el campo del formulario

        # Validar que la consulta de inserción no esté vacía
        if not insert_query:
            return redirect(url_for('index', error="Por favor ingrese una consulta SQL de inserción."))

        try:
            # Conectar a la base de datos SQLite
            conn = sqlite3.connect('database.db')
            c = conn.cursor()

            # Ejecutar la consulta de inserción
            c.execute(insert_query)
            conn.commit()  # Asegúrate de hacer commit para guardar los cambios
            print(f"Datos insertados con éxito: {insert_query}")
            conn.close()

            return redirect(url_for('index', success="Datos insertados correctamente"))

        except Exception as e:
            print(f"Error insertando datos: {str(e)}")
            return redirect(url_for('index', error="Hubo un error al insertar los datos"))

    return render_template_string(HTML_TEMPLATE, query="", results=[], headers=[], tables=[])



@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    if 'file' not in request.files:
        return redirect(request.url)

    file = request.files['file']
    table_name = request.form['table_name']  # Obtener el nombre de la tabla desde el formulario
    print(table_name) #depuración
    
    if file.filename == '' or not table_name:
        return redirect(request.url)

    if file:
        # Guardar el archivo en el servidor
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)

        # Leer el CSV y cargarlo en SQLite
        df = pd.read_csv(file_path)

        # Conectar a la base de datos SQLite
        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        # Crear la tabla dinámicamente según las columnas del CSV
        columns = ', '.join([f"{col} TEXT" for col in df.columns])
        c.execute(f"DROP TABLE IF EXISTS {table_name}")
        c.execute(f"CREATE TABLE {table_name} ({columns})")

        # Insertar los datos del CSV en la tabla
        df.to_sql(table_name, conn, if_exists='replace', index=False)

        # Cerrar la conexión
        conn.close()

        print(f"File saved at: {file_path}")

        return redirect(url_for('index'))


@app.route('/truncate_table/<table_name>', methods=['POST'])
def truncate_table(table_name):
    try:
        # Limpiar el nombre de la tabla: eliminar comas, paréntesis y comillas adicionales
        table_name = table_name.strip("()").strip("'").strip(',').strip("'")
        
        # Conectar a la base de datos SQLite
        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        # Truncar la tabla (vaciarla)
        c.execute(f"DELETE FROM `{table_name}`")
        conn.commit()

        conn.close()

        print(f"Tabla {table_name} truncada.")
    except Exception as e:
        print(f"Error truncando la tabla {table_name}: {str(e)}")

    return redirect(url_for('index'))

@app.route('/drop_table/<table_name>', methods=['POST'])
def drop_table(table_name):
    try:    
        # Limpiar el nombre de la tabla: eliminar comas, paréntesis y comillas adicionales
        table_name = table_name.strip("()").strip("'").strip(',').strip("'")

        # Verificar el nombre de la tabla limpio
        print(f"Intentando eliminar la tabla: {table_name}")

        # Conectar a la base de datos SQLite
        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        # Eliminar la tabla
        query = f"DROP TABLE IF EXISTS `{table_name}`;"  # Usamos backticks para manejar nombres especiales de tablas
        print(f"Ejecutando consulta SQL: {query}")
        c.execute(query)
        conn.commit()

        conn.close()

        print(f"Tabla {table_name} eliminada.")
    except Exception as e:
        print(f"Error eliminando la tabla {table_name}: {str(e)}")

    return redirect(url_for('index'))



if __name__ == '__main__':
    app.run(debug=True)
