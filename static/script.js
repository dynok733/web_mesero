// Datos de usuarios (simulados)
const users = {
    ad: { password: "123", role: "Administrador", id: 1 },
    me: { password: "123", role: "Mesero", id: 2 },
    co: { password: "123", role: "Cocinero", id: 3 }
};

// Manejar el evento del formulario de login
document.getElementById("login-form").addEventListener("submit", function(event) {
    event.preventDefault();
    
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value.trim();
    const errorMessage = document.getElementById("error-message");

    // Validación simple de usuario y contraseña
    if (username && password && users[username] && users[username].password === password) {
        // Guardar el usuario en el localStorage
        localStorage.setItem('loggedUser', JSON.stringify(users[username]));
        // Redirigir al dashboard correspondiente según el rol
        redirectToDashboard(users[username].role);
    } else {
        errorMessage.textContent = "Usuario o contraseña incorrectos.";
    }
});

// Redirigir según el rol
function redirectToDashboard(role) {
    switch (role) {
        case "Administrador":
            window.location.href = "admin_dashboard.html";
            break;
        case "Mesero":
            window.location.href = "mesero_dashboard.html";
            break;
        case "Cocinero":
            window.location.href = "cocinero_dashboard.html";
            break;
        default:
            alert("Error desconocido.");
    }
}
