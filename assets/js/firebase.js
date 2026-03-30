/* ──────────────────────────────────────────────────────────
   CONFIGURACIÓN FIREBASE — RENOVABOT
   Proyecto: bot-apoyo-erradicacion-vicios
────────────────────────────────────────────────────────── */
const firebaseConfig = {
  apiKey: "AIzaSyDlpifktiEE-k2HexCrzjEuVtPG87vGMUc",
  authDomain: "synapse-ftp.firebaseapp.com",
  databaseURL: "https://synapse-ftp-default-rtdb.firebaseio.com",
  projectId: "synapse-ftp",
  storageBucket: "synapse-ftp.firebasestorage.app",
  messagingSenderId: "80708296920",
  appId: "1:80708296920:web:d081cf3b0c1a818859f7ad",
  measurementId: "G-NGYB2YW67V"
};

if (!firebase.apps || !firebase.apps.length) {
  firebase.initializeApp(firebaseConfig);
}

const Database = firebase.database();
const Auth = firebase.auth();