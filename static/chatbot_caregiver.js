/* Caregiver patient selector for chatbot */
(function() {
    var header = document.getElementById('chat-header');
    if (!header) return;

    // Build patient list from the data attribute
    var patientsData = document.getElementById('chat-window').getAttribute('data-patients');
    if (!patientsData) return;

    var patients;
    try { patients = JSON.parse(patientsData); } catch(e) { return; }
    if (!patients || patients.length <= 1) return;

    var select = document.createElement('select');
    select.id = 'chat-patient-select';
    select.style.cssText = 'background: rgba(255,255,255,0.2); color: white; border: 1px solid rgba(255,255,255,0.3); border-radius: 6px; padding: 3px 6px; font-size: 0.75rem; cursor: pointer; max-width: 120px;';

    for (var i = 0; i < patients.length; i++) {
        var opt = document.createElement('option');
        opt.value = patients[i].id;
        opt.textContent = patients[i].name;
        opt.style.color = '#333';
        select.appendChild(opt);
    }

    select.onchange = function() {
        window._chatPatientIdOverride = parseInt(this.value);
    };

    header.children[0].appendChild(select);
})();
