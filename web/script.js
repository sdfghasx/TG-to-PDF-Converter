const btnJson = document.getElementById('btn-json');
const btnPdf = document.getElementById('btn-pdf');
const btnStart = document.getElementById('btn-start');
const btnCalc = document.getElementById('btn-calc');
const inputJson = document.getElementById('json-path');
const inputPdf = document.getElementById('pdf-path');
const dateFrom = document.getElementById('date-from');
const dateTo = document.getElementById('date-to');
const logArea = document.getElementById('log-area');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const calcResult = document.getElementById('calc-result');

function checkReady() { btnStart.disabled = !(inputJson.value && inputPdf.value); }

function setupCustomSelect(wrapperId) {
    const wrapper = document.getElementById(wrapperId);
    const selected = wrapper.querySelector('.select-selected');
    const itemsContainer = wrapper.querySelector('.select-items');
    selected.addEventListener('click', function(e) {
        e.stopPropagation();
        document.querySelectorAll('.select-items').forEach(el => { if(el !== itemsContainer) el.classList.add('select-hide'); });
        itemsContainer.classList.toggle('select-hide');
    });
    itemsContainer.addEventListener('click', function(e) {
        if (e.target.hasAttribute('data-val')) {
            selected.innerHTML = e.target.innerHTML;
            selected.style.fontFamily = e.target.style.fontFamily;
            wrapper.setAttribute('data-value', e.target.getAttribute('data-val'));
            itemsContainer.classList.add('select-hide');
        }
    });
}
setupCustomSelect('wrapper-size');
setupCustomSelect('wrapper-font');
document.addEventListener('click', () => document.querySelectorAll('.select-items').forEach(el => el.classList.add('select-hide')));

async function loadFonts() {
    let fonts = await eel.get_available_fonts()();
    const listFonts = document.getElementById('list-fonts');
    let style = document.createElement('style'); let cssStr = "";
    fonts.forEach(font => {
        cssStr += `@font-face { font-family: '${font.name}'; src: url('fonts/${font.file}'); }\n`;
        let item = document.createElement('div');
        item.setAttribute('data-val', font.name); item.innerText = font.name; item.style.fontFamily = `'${font.name}', sans-serif`;
        listFonts.appendChild(item);
    });
    style.innerHTML = cssStr; document.head.appendChild(style);
}
window.onload = loadFonts;

btnJson.addEventListener('click', async () => {
    let res = await eel.pick_file_json(inputJson.value)();
    if (res) { 
        inputJson.value = res; 
        let defaultPdf = await eel.get_default_pdf_path(res)();
        inputPdf.value = defaultPdf;
        checkReady(); 
        calcResult.style.display = 'none'; 
    }
});

btnPdf.addEventListener('click', async () => {
    let res = await eel.pick_file_pdf(inputPdf.value)();
    if (res) { inputPdf.value = res; checkReady(); }
});

btnCalc.addEventListener('click', async () => {
    if (!inputJson.value) { alert("Сначала выберите JSON файл!"); return; }
    btnCalc.style.opacity = '0.5';
    
    // Берем размер шрифта для точного расчета
    const sizeVal = document.getElementById('wrapper-size').getAttribute('data-value');
    
    let res = await eel.calculate_volume(inputJson.value, dateFrom.value, dateTo.value, sizeVal)();
    btnCalc.style.opacity = '1';
    
    if (res.success) {
        calcResult.style.display = 'block';
        calcResult.innerHTML = `📊 <b>Сообщений:</b> ${res.count} &nbsp;|&nbsp; 📄 <b>~ Страниц:</b> ${res.pages} &nbsp;|&nbsp; 📚 <b>Томов:</b> ${res.vols}`;
    } else {
        alert("Ошибка анализа: " + res.error);
    }
});

btnStart.addEventListener('click', () => {
    btnStart.disabled = true; btnJson.disabled = true; btnPdf.disabled = true;
    logArea.value = "> Инициализация сборки...\n";
    statusDot.className = "dot pulsing"; statusText.innerText = "Генерация PDF...";
    
    const fontVal = document.getElementById('wrapper-font').getAttribute('data-value');
    const sizeVal = document.getElementById('wrapper-size').getAttribute('data-value');
    const theme = document.getElementById('check-theme').checked ? 'dark' : 'light';
    
    const showMedia = document.getElementById('check-media').checked;
    const showTop = document.getElementById('check-top').checked;
    const showWatermark = document.getElementById('check-watermark').checked;
    const showCharts = document.getElementById('check-charts').checked;
    const showWordcloud = document.getElementById('check-wordcloud').checked;
    const showToc = document.getElementById('check-toc').checked;
    const showLinks = document.getElementById('check-links').checked;
    
    eel.start_conversion(
        inputJson.value, inputPdf.value, 
        dateFrom.value, dateTo.value, 
        fontVal, sizeVal, theme, 
        showMedia, showTop, showWatermark, showCharts, showWordcloud, showToc, showLinks
    )();
});

eel.expose(addLog); function addLog(msg) { logArea.value += msg + "\n"; logArea.scrollTop = logArea.scrollHeight; }
eel.expose(updateStatus); function updateStatus(status, text, color) { statusDot.className = "dot " + status; statusText.innerText = text; statusText.style.color = color || "var(--text-muted)"; }
eel.expose(enableButton); function enableButton() { btnStart.disabled = false; btnJson.disabled = false; btnPdf.disabled = false; }