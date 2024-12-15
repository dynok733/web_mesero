import mysql.connector
from mysql.connector import Error
from flask import Flask, render_template, request, redirect, url_for, session
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta'

# Función para obtener la conexión con la base de datos
def get_db():
    try:
        connection = mysql.connector.connect(
            host='database-mario.ct8s48kk2drd.us-east-2.rds.amazonaws.com',
            database='nuevo_restaurante',
            user='adminsay',  # Cambia esto a tu usuario de MySQL
            password='C43t0555'  # Cambia esto a tu contraseña de MySQL
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

# Función para obtener el menú desde la base de datos
def obtener_menu():
    db = get_db()
    if db:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM menu")
        menu = cursor.fetchall()
        cursor.close()
        db.close()
        return menu

# Ruta principal para el cliente
@app.route('/')
def index():
    menu = obtener_menu()  # Obtenemos los productos del menú
    return render_template('index.html', menu=menu)

# Ruta para realizar un pedido
@app.route('/realizar_pedido', methods=['POST'])
def realizar_pedido():
    nombre_cliente = request.form['nombre_cliente']  # Obtener el nombre del cliente ingresado

    db = get_db()
    cursor = db.cursor()

    total = 0  # Para almacenar el total de la orden
    productos_pedidos = []  # Lista para almacenar los productos que se han pedido
    
    menu = obtener_menu()  # Obtenemos el menú

    # Recibir los productos y cantidades desde el formulario
    for producto in menu:
        cantidad = request.form.get(f'producto_{producto["id"]}', type=int, default=0)
        if cantidad > 0:
            total += producto["precio"] * cantidad  # Sumar al total
            productos_pedidos.append({
                "nombre": producto["nombre"],
                "cantidad": cantidad,
                "precio": producto["precio"]
            })
            cursor.execute("INSERT INTO ordenes (nombre_cliente, estado) VALUES (%s, %s)", (nombre_cliente, 'Pendiente'))
            db.commit()
            id_orden = cursor.lastrowid  # Obtener el ID de la orden recién insertada
            
            # Insertar los detalles de la orden (productos y cantidades)
            cursor.execute("INSERT INTO detalle_ordenes (id_orden, id_producto, cantidad) VALUES (%s, %s, %s)", 
                           (id_orden, producto["id"], cantidad))
            db.commit()

    cursor.close()
    db.close()

    # Ahora, pasamos la información correcta a la plantilla
    return render_template('resumen_pedido.html', productos=productos_pedidos, total=total, nombre_cliente=nombre_cliente)

@app.route('/pagar', methods=['POST'])
def pagar():
    nombre_cliente = request.form['nombre_cliente']
    db = get_db()
    cursor = db.cursor(dictionary=True)  # Usamos el cursor con dictionary=True

    total = 0
    productos_pedidos = []

    # Obtener los productos de la base de datos para esta orden
    cursor.execute(""" 
        SELECT p.nombre, d.cantidad, p.precio 
        FROM detalle_ordenes d 
        JOIN menu p ON d.id_producto = p.id 
        WHERE d.id_orden IN (SELECT id FROM ordenes WHERE nombre_cliente = %s)
    """, (nombre_cliente,))
    productos = cursor.fetchall()  # Ahora es una lista de diccionarios

    # Calcular el total de la orden
    total = sum(producto['cantidad'] * producto['precio'] for producto in productos)
    
    productos_pedidos = [{
        'nombre': producto['nombre'],
        'cantidad': producto['cantidad'],
        'precio': producto['precio']
    } for producto in productos]

    # Cambiar el estado de la orden a "Pagada"
    cursor.execute("UPDATE ordenes SET estado = 'Pendiente' WHERE nombre_cliente = %s", (nombre_cliente,))
    db.commit()
    cursor.close()
    db.close()

    # Generar el ticket como PDF usando ReportLab
    ticket_path = generar_ticket_pdf(nombre_cliente, productos_pedidos, total)

    # Redirigir a la página principal (index)
    return redirect(url_for('index'))

# Función para generar el ticket PDF usando ReportLab
def generar_ticket_pdf(nombre_cliente, productos, total):
    ticket_path = os.path.join('static', f'ticket_{nombre_cliente}.pdf')
    c = canvas.Canvas(ticket_path, pagesize=letter)
    c.setFont("Helvetica", 12)

    # Escribir el encabezado del ticket
    c.drawString(100, 750, f"Ticket para {nombre_cliente}")
    c.drawString(100, 735, "-----------------------------------")

    y_position = 715  # Posición inicial para escribir los productos

    # Escribir los productos en el ticket
    for producto in productos:
        c.drawString(100, y_position, f"{producto['nombre']} x{producto['cantidad']} - ${producto['precio'] * producto['cantidad']}")
        y_position -= 20

    c.drawString(100, y_position - 20, f"Total: ${total}")

    c.save()

    return ticket_path

# Rutas para administración
@app.route('/admin/pendientes')
def ordenes_pendientes_view():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Obtener las órdenes pendientes
    cursor.execute(""" 
        SELECT o.id, o.nombre_cliente, SUM(p.precio * d.cantidad) AS total, o.estado FROM ordenes o 
        JOIN detalle_ordenes d ON o.id = d.id_orden 
        JOIN menu p ON d.id_producto = p.id 
        WHERE o.estado = 'Pendiente' GROUP BY o.id
    """)
    ordenes_pendientes = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template('ordenes_pendientes.html', ordenes_pendientes=ordenes_pendientes)

@app.route('/admin/completadas')
def ordenes_completadas_view():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Obtener las órdenes completadas
    cursor.execute(""" 
        SELECT o.id, o.nombre_cliente, SUM(p.precio * d.cantidad) AS total, o.estado FROM ordenes o 
        JOIN detalle_ordenes d ON o.id = d.id_orden 
        JOIN menu p ON d.id_producto = p.id 
        WHERE o.estado = 'Completada' GROUP BY o.id
    """)
    ordenes_completadas = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template('ordenes_completadas.html', ordenes_completadas=ordenes_completadas)

# Ruta para la vista del login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        cursor.close()
        
        if user:
            session['user_id'] = user['id']
            session['role'] = user['role']
            return redirect(url_for('ordenes_pendientes_view') if user['role'] == 'admin' else url_for('cocinero'))
        else:
            return "Credenciales incorrectas", 403
    
    return render_template('login.html')
@app.route('/cocinero')
def cocinero():
    if 'role' not in session or session['role'] != 'cocinero':
        return redirect(url_for('login'))

    # Obtener solo las órdenes con estado 'Pendiente'
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Obtener las órdenes pendientes para el cocinero
    cursor.execute(""" 
        SELECT o.id, o.nombre_cliente, o.estado, p.nombre, d.cantidad, p.precio
        FROM ordenes o
        JOIN detalle_ordenes d ON o.id = d.id_orden
        JOIN menu p ON d.id_producto = p.id
        WHERE o.estado = 'Pendiente'
    """)
    ordenes = cursor.fetchall()
    cursor.close()
    db.close()

    # Agrupar las órdenes por cliente
    ordenes_cliente = {}

    for orden in ordenes:
        cliente_nombre = orden['nombre_cliente']
        if cliente_nombre not in ordenes_cliente:
            ordenes_cliente[cliente_nombre] = {
                'cliente': cliente_nombre,
                'ordenes': []
            }

        ordenes_cliente[cliente_nombre]['ordenes'].append({
            'id': orden['id'],
            'estado': orden['estado'],
            'producto': orden['nombre'],
            'cantidad': orden['cantidad'],
            'precio': orden['precio'],
            'total': orden['cantidad'] * orden['precio']
        })

    return render_template('cocinero.html', ordenes_cliente=ordenes_cliente)

@app.route('/actualizar_orden/<int:id_orden>', methods=['POST'])
def actualizar_orden(id_orden):
    nuevo_estado = request.form['estado']
    db = get_db()
    if db:
        cursor = db.cursor()
        cursor.execute("UPDATE ordenes SET estado = %s WHERE id = %s", (nuevo_estado, id_orden))
        db.commit()
        cursor.close()
        db.close()
    return redirect(url_for('cocinero'))

# Ruta de cierre de sesión (Logout)
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))  # Redirige a la página de login

# Función para obtener órdenes por estado
def obtener_ordenes_por_estado(estado):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM ordenes WHERE estado = %s", (estado,))
    ordenes = cursor.fetchall()
    cursor.close()
    db.close()
    return ordenes


@app.route('/admin/usuarios', methods=['GET'])
def ver_usuarios():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios")
    usuarios = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template('usuarios.html', usuarios=usuarios)


@app.route('/admin/usuarios/nuevo', methods=['GET', 'POST'])
def nuevo_usuario():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO usuarios (username, password, role) VALUES (%s, %s, %s)",
                       (username, password, role))
        db.commit()
        cursor.close()
        db.close()

        return redirect(url_for('ver_usuarios'))

    return render_template('nuevo_usuario.html')


@app.route('/admin/usuarios/editar/<int:id>', methods=['GET', 'POST'])
def editar_usuario(id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Obtener el usuario a editar
    cursor.execute("SELECT * FROM usuarios WHERE id = %s", (id,))
    usuario = cursor.fetchone()

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        # Actualizar el usuario
        cursor.execute("UPDATE usuarios SET username = %s, password = %s, role = %s WHERE id = %s",
                       (username, password, role, id))
        db.commit()
        cursor.close()
        db.close()

        return redirect(url_for('ver_usuarios'))

    cursor.close()
    db.close()
    return render_template('editar_usuario.html', usuario=usuario)


@app.route('/admin/usuarios/eliminar/<int:id>', methods=['POST'])
def eliminar_usuario(id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM usuarios WHERE id = %s", (id,))
    db.commit()
    cursor.close()
    db.close()

    return redirect(url_for('ver_usuarios'))
from werkzeug.utils import secure_filename


app.config['UPLOAD_FOLDER'] = 'static/uploads/'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# Asegurarse de que la carpeta uploads exista
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])



# Ruta para ver todos los productos
@app.route('/admin/menu', methods=['GET'])
def ver_menu():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM menu")
    productos = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template('menu.html', productos=productos)

# Ruta para agregar un nuevo producto
@app.route('/admin/productos/nuevo', methods=['GET', 'POST'])
def nuevo_producto():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        categoria = request.form['categoria']
        nombre = request.form['nombre']
        precio = request.form['precio']
        imagen = request.files.get('imagen')  # Usamos .get() para obtener la imagen de manera más segura

        # Guardar la imagen en el directorio 'uploads' si se ha subido una imagen
        if imagen:
            filename = secure_filename(imagen.filename)
            imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            imagen.save(imagen_path)
            imagen_db_path = f"uploads/{filename}"  # Guardar solo la ruta relativa
        else:
            imagen_db_path = None

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO menu (categoria, nombre, precio, imagen) VALUES (%s, %s, %s, %s)",
            (categoria, nombre, precio, imagen_db_path)  # Usar imagen_db_path aquí
        )
        db.commit()
        cursor.close()
        db.close()

        return redirect(url_for('ver_menu'))

    return render_template('nuevo_producto.html')


# Ruta para editar un producto
@app.route('/admin/productos/editar/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM menu WHERE id = %s", (id,))
    producto = cursor.fetchone()

    if request.method == 'POST':
        categoria = request.form['categoria']
        nombre = request.form['nombre']
        precio = request.form['precio']
        imagen = request.files.get('imagen')

        # Si se sube una nueva imagen, se guarda en 'uploads'
        if imagen:
            filename = secure_filename(imagen.filename)
            imagen.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            imagen_db_path = f"uploads/{filename}"  # Guardar solo la ruta relativa
        else:
            imagen_db_path = producto['imagen']  # Mantener la imagen actual

        # Actualizar producto
        cursor.execute(
            "UPDATE menu SET categoria = %s, nombre = %s, precio = %s, imagen = %s WHERE id = %s",
            (categoria, nombre, precio, imagen_db_path, id)  # Usar imagen_db_path aquí
        )
        db.commit()
        cursor.close()
        db.close()

        return redirect(url_for('ver_menu'))

    cursor.close()
    db.close()
    return render_template('editar_producto.html', producto=producto)

# Ruta para eliminar un producto
@app.route('/admin/productos/eliminar/<int:id>', methods=['POST'])
def eliminar_producto(id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM menu WHERE id = %s", (id,))
    db.commit()
    cursor.close()
    db.close()

    return redirect(url_for('ver_menu'))
if __name__ == "__main__":
    app.run(debug=True)
