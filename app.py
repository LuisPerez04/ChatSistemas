from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from base64 import b64encode
import os
from flask_session import Session  # Importa la extensión Flask-Session
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root@localhost/chat'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'clave_secreta'  # Agrega la clave secreta para Flask
app.config['SESSION_TYPE'] = 'filesystem'  # Configura el tipo de almacenamiento de sesión
db = SQLAlchemy(app)
socketio = SocketIO(app)  # Inicializa SocketIO con la aplicación Flask
Session(app)  # Inicializa la extensión Flask-Session

# Define el modelo de la base de datos
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    telefono = db.Column(db.String(20), unique=True)  # Asegura que el número de teléfono sea único
    fecha_nacimiento = db.Column(db.Date)
    perfil = db.Column(db.LargeBinary)  # Almacenamiento de imagen en formato BLOB
    color = db.Column(db.String(7))  # Campo para almacenar el color del usuario

    def __repr__(self):
        return f'<Usuario {self.nombre}>'
    
class Mensaje(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contenido = db.Column(db.String(500))
    fecha_envio = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Mensaje {self.id}>'


# Función para guardar la imagen en formato BLOB
def guardar_imagen(imagen):
    # Directorio donde se guardarán las imágenes
    directorio_uploads = os.path.join(app.root_path, 'uploads')

    # Verificar si el directorio 'uploads' existe, si no, crearlo
    if not os.path.exists(directorio_uploads):
        os.makedirs(directorio_uploads)

    imagen_binaria = imagen.read()
    return imagen_binaria

historial_mensajes = []  # Lista para almacenar los mensajes

@app.route('/', methods=['GET', 'POST'])
def inicio():
    mensaje_error = None  # Inicializa el mensaje de error como None
    if request.method == 'POST':
        telefono = request.form['telefono']
        nombre = request.form['nombre_completo']

        # Verifica si las credenciales son correctas
        usuario = Usuario.query.filter_by(telefono=telefono, nombre=nombre).first()
        if usuario:
            # Almacena el ID del usuario en la sesión
            session['usuario_id'] = usuario.id
            return redirect(url_for('perfil_usuario'))  # Redirige al perfil si las credenciales son correctas
        else:
            mensaje_error = "Credenciales incorrectas"  # Mensaje de error si las credenciales son incorrectas

    return render_template('inicio.html', mensaje_error=mensaje_error)  # Renderiza la plantilla de inicio de sesión con el mensaje de error

@app.route('/desconectar')
def desconectar():
    # Obtiene el ID del usuario de la sesión
    usuario_id = session.get('usuario_id')
    if usuario_id:
        # Redirige al perfil basado en el ID del usuario
        return redirect(url_for('perfil_usuario', usuario_id=usuario_id))
    else:
        # Si no hay ID de usuario en la sesión, redirige a la página de inicio
        return redirect(url_for('inicio'))

@app.route('/perfil_usuario')
def perfil_usuario():
    usuario_id = session.get('usuario_id')
    if usuario_id:
        usuario = Usuario.query.get(usuario_id)
        if usuario:
            # Convertir el BLOB de la imagen a una cadena Base64
            imagen_base64 = b64encode(usuario.perfil).decode('utf-8')
            return render_template('perfil.html', usuario=usuario, imagen_base64=imagen_base64)
        else:
            return redirect(url_for('inicio'))
    else:
        return redirect(url_for('inicio'))

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre_completo']
        telefono = request.form['telefono']
        fecha_nacimiento = request.form['fecha_nacimiento']
        perfil = request.files['imagen_perfil']
        color_seleccionado = request.form['color']
        
        if not nombre or not telefono or not fecha_nacimiento or not perfil:
            return 'Todos los campos son obligatorios', 400

        # Verifica si el número de teléfono ya está registrado en la base de datos
        if Usuario.query.filter_by(telefono=telefono).first():
            return redirect(url_for('inicio'))  # Redirige a la página de inicio si el número de teléfono ya está registrado

        imagen_blob = guardar_imagen(perfil)

        nuevo_usuario = Usuario(nombre=nombre, telefono=telefono, fecha_nacimiento=fecha_nacimiento, perfil=imagen_blob, color=color_seleccionado)
        db.session.add(nuevo_usuario)
        db.session.commit()

        # Almacena el número de teléfono del usuario en la sesión
        session['usuario_id'] = nuevo_usuario.id

        return redirect(url_for('perfil_usuario'))  # Redirige al perfil basado en el ID del usuario

    return render_template('registro.html')

@app.route('/chat')
def chat():
    historial_mensajes = Mensaje.query.all()
    return render_template('chat.html', historial_mensajes=historial_mensajes)

@socketio.on('message')
def handle_message(message):
    print('Mensaje recibido:', message)
    # Obtiene el color del usuario de la base de datos
    usuario_id = session.get('usuario_id')
    usuario = Usuario.query.get(usuario_id)
    color_usuario = usuario.color if usuario else 'black'  # Si no se encuentra el usuario, usa un color por defecto

    nuevo_mensaje = Mensaje(contenido=message['message'])  # Extrae el contenido del mensaje
    db.session.add(nuevo_mensaje)
    db.session.commit()
    socketio.emit('message', {'message': message['message'], 'sender': usuario.nombre if usuario else 'Anónimo', 'color': color_usuario})

@app.route('/perfil/<telefono>')
def perfil_usuario_por_telefono(telefono):
    usuario = Usuario.query.filter_by(telefono=telefono).first_or_404()
    return redirect(url_for('perfil_usuario', usuario_id=usuario.id))

if __name__ == '__main__':
    socketio.run(app, debug=True)