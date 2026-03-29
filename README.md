# 🌱 RenovaBot — Bot de Apoyo para Erradicación de Vicios

Bot de Telegram + Panel Administrativo Web para apoyar a personas en el proceso de superar hábitos o adicciones, con seguimiento diario, sistema de retos, XP, rachas, ayudantes y monitoreo en tiempo real.

---

## Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Bot Telegram | `python-telegram-bot` v21 (Webhook) |
| Backend / API | Python + Flask |
| Base de Datos | Firebase Realtime Database |
| Autenticación Admin | Firebase Authentication (Email/Password) |
| Scheduler | APScheduler |
| Frontend | HTML + CSS Vanilla + JavaScript |
| Despliegue | Render (Web Service) |

---

## Estructura del Proyecto

```
bot_apoyo_erradicacion_vicios/
├── app/
│   ├── bot/
│   │   ├── handlers.py      # Comandos /start, /progreso, callbacks
│   │   ├── keyboards.py     # Teclados inline
│   │   └── main.py          # Inicialización del bot y webhook
│   ├── api/
│   │   └── main.py          # Flask API + rutas del panel admin
│   ├── services/
│   │   ├── firebase_db.py   # CRUD Firebase Realtime Database
│   │   ├── messages.py      # Motor de mensajes motivacionales
│   │   ├── missions.py      # Sistema de misiones
│   │   ├── xp_system.py     # XP, niveles y rachas
│   │   ├── invitations.py   # Links de invitación para ayudantes
│   │   ├── relapse.py       # Lógica de recaídas y recuperación
│   │   └── escrow.py        # Stub de retención/compromiso
│   ├── worker/
│   │   └── scheduler.py     # APScheduler con 4 jobs
│   └── config.py            # Variables de entorno
├── assets/
│   ├── css/style.css        # Estilos del panel admin
│   └── js/
│       ├── firebase.js      # SDK Firebase (cliente)
│       └── script.js        # Lógica del panel admin
├── templates/
│   └── admin/
│       └── panel.html       # Dashboard administrativo
├── index.html               # Página de login
├── run.py                   # Punto de entrada
├── requirements.txt
├── Procfile                 # Para Render
├── .env.example             # Plantilla de variables de entorno
└── firebase_rules.json      # Reglas de seguridad de Realtime DB
```

---

## Configuración Inicial

### 1. Firebase

1. Ve a [Firebase Console](https://console.firebase.google.com/)
2. Crea un proyecto (o usa uno existente)
3. Habilita **Realtime Database** y copia la URL
4. Ve a **Authentication → Sign-in method** y habilita Email/Password
5. Crea un usuario admin: **Authentication → Users → Add User**
6. Ve a **Configuración del Proyecto → Cuentas de Servicio → Generar nueva clave privada**
7. Guarda el JSON como `firebase_credentials.json` en la raíz del proyecto
8. Ve a **Realtime Database → Reglas** y pega el contenido de `firebase_rules.json`

### 2. Firebase (cliente JS - Panel Admin)

Edita `assets/js/firebase.js` con los datos de tu proyecto (los encuentras en **Configuración del Proyecto → Tus aplicaciones → Web**).

### 3. Bot de Telegram

1. Habla con [@BotFather](https://t.me/BotFather)
2. Crea un nuevo bot con `/newbot`
3. Copia el token y ponlo en `.env`
4. En `app/services/invitations.py`, reemplaza `TU_BOT_USERNAME` por el username real de tu bot

### 4. Variables de Entorno

Copia `.env.example` como `.env` y completa todos los valores:

```bash
cp .env.example .env
```

---

## Instalación Local

```bash
pip install -r requirements.txt
python run.py
```

Para pruebas locales del webhook, puedes usar [ngrok](https://ngrok.com/):
```bash
ngrok http 10000
# Copia la URL HTTPS y úsala como WEBHOOK_URL en .env
```

---

## Despliegue en Render

1. Sube el proyecto a un repositorio de GitHub
2. En Render: **New → Web Service → Connect to GitHub repo**
3. Configura:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python run.py`
4. Agrega todas las variables de entorno del `.env.example` en el panel de Render
5. Para `firebase_credentials.json`: puedes agregar su contenido como variable de entorno `FIREBASE_CREDENTIALS_JSON` y cargarlo con código, o subirlo directamente (sin incluir en git)

---

## Comandos del Bot

| Comando | Descripción |
|---------|------------|
| `/start` | Inicia el flujo de registro o retoma el plan |
| `/help` | Muestra la ayuda |
| `/estado` | Estado actual del plan |
| `/progreso` | Resumen de XP, nivel y racha |
| `/misiones` | Misiones del día |
| `/recaida` | Reportar una recaída |
| `/ayuda` | Solicitar apoyo de emergencia |
| `/configurar` | Opciones del plan |

---

## Flujo de Usuario

```
/start
  └── Selecciona vicio/hábito
        └── Selecciona duración (5-12 meses)
              └── Selecciona número de ayudantes (0-2)
                    ├── Genera link de invitación para ayudantes
                    └── Plan iniciado → menú principal con botones
                          ├── Ver misiones (con botón completar)
                          ├── Ver progreso (XP, racha, nivel)
                          ├── Pedir ayuda (modo crisis)
                          ├── Respirar (ejercicio guiado)
                          ├── Reportar recaída (sin borrar progreso)
                          ├── Pausar plan
                          └── Llamar ayudante
```

---

## Sistema de XP y Niveles

| Nivel | Nombre | XP Requerida |
|-------|--------|-------------|
| 1 | Iniciado | 0 |
| 2 | Decidido | 50 |
| 3 | Firme | 150 |
| 4 | Resistente | 300 |
| 5 | Constante | 500 |
| 6 | Tenaz | 800 |
| 7 | Inquebrantable | 1200 |
| 8 | Inspirador | 1800 |
| 9 | Campeón | 2600 |
| 10 | Leyenda | 3600 |

### Recompensas
- Misión completada: +10 XP
- Día sin consumo: +20 XP
- Racha semanal: +50 XP bonus
- Racha mensual: +200 XP bonus
- Recaída: -15 XP (suave, nunca destruye progreso)

---

## Frecuencia de Mensajes (según fase)

| Fase | Intervalo |
|------|-----------|
| Días 1-3 | Cada 3 minutos |
| Semana 1 (días 4-7) | Cada 10 minutos |
| Semana 2 (días 8-14) | Cada 30 minutos |
| Semana 3 en adelante | Cada 60 minutos |
| Mes 2 en adelante | Cada 120 minutos |

---

## Mejoras Futuras

- [ ] Inteligencia Artificial para respuestas personalizadas (Gemini API)
- [ ] Gráficos interactivos de progreso en el panel (Chart.js)
- [ ] Integración real con proveedor de escrow/compromiso (Stripe Escrow, escrow.com)
- [ ] Exportación de datos a CSV/Excel desde el panel
- [ ] Notificaciones push web para el administrador
- [ ] Modo multi-idioma (EN/ES)
- [ ] App móvil (Telegram Mini App)
- [ ] Sistema de comunidad anónima entre usuarios para apoyo mutuo
- [ ] Integración con profesionales de salud mental (agenda de sesiones)

---

## Licencia

MIT — Uso libre con atribución.
