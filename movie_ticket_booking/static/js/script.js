// Register form validation
function validateRegister() {
    const name = document.getElementById('name').value;
    const phone = document.getElementById('phno').value;
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    if (!name || !phone || !email || !password) {
        alert("All fields are required!");
        return false;
    }

    const phonePattern = /^[0-9]{10}$/;
    if (!phone.match(phonePattern)) {
        alert("Please enter a valid phone number!");
        return false;
    }

    return true;
}

// Login form validation
function validateLogin() {
    const name = document.getElementsByName('name')[0].value;
    const password = document.getElementsByName('password')[0].value;

    if (!name || !password) {
        alert("All fields are required!");
        return false;
    }

    return true;
}
