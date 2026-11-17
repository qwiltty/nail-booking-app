// Telegram WebApp SDK
const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

// Состояние
const state = {
  selectedService: null,
  selectedDate: null,
  selectedSlot: null,
  referenceFile: null,
  services: []
};

// DOM Элементы
const manicureGroup = document.getElementById('manicure-group');
const extensionsGroup = document.getElementById('extensions-group');
const daysRow = document.getElementById('days-row');
const timesGrid = document.getElementById('times-grid');
const labelSelectedDate = document.getElementById('label-selected-date');

const inpName = document.getElementById('inp-name');
const inpPhone = document.getElementById('inp-phone');
const inpTg = document.getElementById('inp-tg');
const inpComment = document.getElementById('inp-comment');

const uploaderBox = document.getElementById('uploader-box');
const filePhoto = document.getElementById('file-photo');
const uploaderPrompt = document.getElementById('uploader-prompt');
const uploaderPreview = document.getElementById('uploader-preview');
const previewImageElem = document.getElementById('preview-image-elem');
const btnRemovePhoto = document.getElementById('btn-remove-photo');

const barTitle = document.getElementById('bar-title');
const barDetail = document.getElementById('bar-detail');
const btnSubmit = document.getElementById('btn-submit');

const modalSuccess = document.getElementById('modal-success');
const modalSummary = document.getElementById('modal-summary');
const btnModalClose = document.getElementById('btn-modal-close');

// Автозаполнение из Telegram
function initTelegramData() {
  if (tg?.initDataUnsafe?.user) {
    const u = tg.initDataUnsafe.user;
    if (u.first_name) {
      inpName.value = `${u.first_name} ${u.last_name || ''}`.trim();
    }
    if (u.username) {
      inpTg.value = `@${u.username}`;
    }
  }
}

// Загрузка услуг
async function loadServices() {
  try {
    const res = await fetch('/api/services');
    const data = await res.json();
    state.services = data.services || [];
    renderServices();
  } catch (err) {
    console.error('Ошибка загрузки прайса:', err);
  }
}

function renderServices() {
  manicureGroup.innerHTML = '';
  extensionsGroup.innerHTML = '';

  state.services.forEach(srv => {
    const row = document.createElement('div');
    row.className = `service-row ${state.selectedService?.id === srv.id ? 'selected' : ''}`;
    row.dataset.id = srv.id;

    // Нижний регистр названия в стиле оригинала ("с покрытием", "без дизайна")
    const displayTitle = srv.title.toLowerCase();

    row.innerHTML = `
      <div class="service-top-line">
        <span class="service-name">${displayTitle}</span>
        <span class="service-dots"></span>
        <span class="service-price">${srv.price}</span>
      </div>
      ${srv.description ? `<div class="service-subtext">${srv.description}</div>` : ''}
    `;

    row.addEventListener('click', () => {
      state.selectedService = srv;
      tg?.HapticFeedback?.impactOccurred('light');
      renderServices();
      updateBar();
      validateForm();
    });

    if (srv.category.toLowerCase().includes('маникюр')) {
      manicureGroup.appendChild(row);
    } else {
      extensionsGroup.appendChild(row);
    }
  });
}

// Календарь на 14 дней
function initDays() {
  daysRow.innerHTML = '';
  const weekdays = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
  const today = new Date();

  for (let i = 0; i < 14; i++) {
    const d = new Date();
    d.setDate(today.getDate() + i);

    const dateStr = d.toISOString().split('T')[0];
    const isFirst = i === 0;

    const item = document.createElement('div');
    item.className = `day-item ${isFirst ? 'active' : ''}`;
    item.dataset.date = dateStr;

    item.innerHTML = `
      <div class="dow">${weekdays[d.getDay()]}</div>
      <div class="num">${d.getDate()}</div>
    `;

    item.addEventListener('click', () => {
      document.querySelectorAll('.day-item').forEach(el => el.classList.remove('active'));
      item.classList.add('active');
      state.selectedDate = dateStr;
      state.selectedSlot = null;
      tg?.HapticFeedback?.impactOccurred('light');
      loadSlots(dateStr, d);
      updateBar();
      validateForm();
    });

    daysRow.appendChild(item);

    if (isFirst) {
      state.selectedDate = dateStr;
      loadSlots(dateStr, d);
    }
  }
}

// Слоты на день
async function loadSlots(dateStr, dateObj) {
  const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
  labelSelectedDate.textContent = `${dateObj.getDate()} ${months[dateObj.getMonth()]}`;

  timesGrid.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; color: var(--color-text-muted); font-size: 13px; padding: 12px;">Загрузка окошек...</div>';

  try {
    const res = await fetch(`/api/slots?date=${dateStr}`);
    const data = await res.json();
    const slots = data.slots || [];

    if (slots.length === 0) {
      timesGrid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; color: var(--color-text-muted); font-size: 12px; padding: 16px; background: #fff; border-radius: 12px; border: 1px dashed var(--color-border);">
          На этот день нет свободных окошек.<br>Выберите другой день.
        </div>
      `;
      return;
    }

    timesGrid.innerHTML = '';
    slots.forEach(slot => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = `time-slot-btn ${state.selectedSlot?.id === slot.id ? 'selected' : ''}`;
      btn.textContent = slot.slot_time;

      btn.addEventListener('click', () => {
        document.querySelectorAll('.time-slot-btn').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        state.selectedSlot = slot;
        tg?.HapticFeedback?.impactOccurred('medium');
        updateBar();
        validateForm();
      });

      timesGrid.appendChild(btn);
    });

  } catch (err) {
    timesGrid.innerHTML = '<div style="grid-column: 1 / -1; color: red; font-size: 12px;">Ошибка загрузки слотов</div>';
  }
}

// Загрузка референса
uploaderBox.addEventListener('click', (e) => {
  if (e.target !== btnRemovePhoto) {
    filePhoto.click();
  }
});

filePhoto.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;

  state.referenceFile = file;
  const reader = new FileReader();
  reader.onload = (event) => {
    previewImageElem.src = event.target.result;
    uploaderPreview.style.display = 'inline-block';
    uploaderPrompt.style.display = 'none';
  };
  reader.readAsDataURL(file);
});

btnRemovePhoto.addEventListener('click', (e) => {
  e.stopPropagation();
  state.referenceFile = null;
  filePhoto.value = '';
  uploaderPreview.style.display = 'none';
  uploaderPrompt.style.display = 'block';
});

// Обновление плавающей полоски
function updateBar() {
  if (state.selectedService) {
    barTitle.textContent = state.selectedService.title;
    const timeInfo = state.selectedSlot ? ` • ${state.selectedSlot.slot_time}` : '';
    barDetail.textContent = `${state.selectedService.price}${timeInfo}`;
  } else {
    barTitle.textContent = 'Выберите услугу';
    barDetail.textContent = 'и свободное время';
  }
}

// Валидация
function validateForm() {
  const ok = state.selectedService && 
             state.selectedSlot && 
             inpName.value.trim().length >= 2 && 
             inpPhone.value.trim().length >= 6;
  btnSubmit.disabled = !ok;
}

[inpName, inpPhone].forEach(input => {
  input.addEventListener('input', validateForm);
});

// Отправка записи
btnSubmit.addEventListener('click', async () => {
  if (btnSubmit.disabled) return;

  btnSubmit.disabled = true;
  btnSubmit.textContent = 'Оформление...';

  const formData = new FormData();
  formData.append('service_id', state.selectedService.id);
  formData.append('slot_id', state.selectedSlot.id);
  formData.append('client_name', inpName.value.trim());
  formData.append('client_phone', inpPhone.value.trim());
  formData.append('client_telegram', inpTg.value.trim());
  formData.append('client_comment', inpComment.value.trim());

  if (state.referenceFile) {
    formData.append('reference_photo', state.referenceFile);
  }

  try {
    const res = await fetch('/api/book', {
      method: 'POST',
      body: formData
    });

    const data = await res.json();

    if (!res.ok) {
      alert(data.detail || 'Ошибка при записи');
      btnSubmit.disabled = false;
      btnSubmit.textContent = 'Записаться';
      return;
    }

    tg?.HapticFeedback?.notificationOccurred('success');

    const b = data.booking;
    modalSummary.innerHTML = `
      <div><b>Услуга:</b> ${b.service_title} (${b.service_price})</div>
      <div style="margin-top: 4px;"><b>Время:</b> ${b.slot_date} в ${b.slot_time}</div>
      <div style="margin-top: 4px;"><b>Клиент:</b> ${b.client_name}</div>
      ${state.referenceFile ? '<div style="margin-top: 6px; color: var(--color-primary); font-size: 12px;">📸 Референс передан мастеру</div>' : ''}
    `;

    modalSuccess.style.display = 'flex';

  } catch (err) {
    alert('Не удалось отправить запись. Проверьте соединение.');
    btnSubmit.disabled = false;
    btnSubmit.textContent = 'Записаться';
  }
});

btnModalClose.addEventListener('click', () => {
  modalSuccess.style.display = 'none';
  if (tg) {
    tg.close();
  } else {
    window.location.reload();
  }
});

// Старт
document.addEventListener('DOMContentLoaded', () => {
  initTelegramData();
  loadServices();
  initDays();
});
