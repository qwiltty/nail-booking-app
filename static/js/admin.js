// DOM Элементы
const tabSlotsBtn = document.getElementById('tab-slots-btn');
const tabBookingsBtn = document.getElementById('tab-bookings-btn');
const viewSlots = document.getElementById('view-slots');
const viewBookings = document.getElementById('view-bookings');

const adminDatePicker = document.getElementById('admin-date-picker');
const customTimeInput = document.getElementById('custom-time-input');
const addCustomSlotBtn = document.getElementById('add-custom-slot-btn');
const adminSlotsList = document.getElementById('admin-slots-list');
const adminBookingsList = document.getElementById('admin-bookings-list');

const lightbox = document.getElementById('lightbox');
const lightboxImg = document.getElementById('lightbox-img');

// Переключение вкладок
tabSlotsBtn.addEventListener('click', () => {
  tabSlotsBtn.classList.add('active');
  tabBookingsBtn.classList.remove('active');
  viewSlots.style.display = 'block';
  viewBookings.style.display = 'none';
  loadAdminSlots();
});

tabBookingsBtn.addEventListener('click', () => {
  tabBookingsBtn.classList.add('active');
  tabSlotsBtn.classList.remove('active');
  viewSlots.style.display = 'none';
  viewBookings.style.display = 'block';
  loadAdminBookings();
});

// Инициализация даты
function initDate() {
  const today = new Date();
  adminDatePicker.value = today.toISOString().split('T')[0];
  adminDatePicker.addEventListener('change', loadAdminSlots);
}

// Загрузка слотов на выбранную дату
async function loadAdminSlots() {
  const dateStr = adminDatePicker.value;
  if (!dateStr) return;

  adminSlotsList.innerHTML = '<div style="text-align: center; color: var(--color-text-muted); padding: 16px;">Загрузка слотов...</div>';

  try {
    const res = await fetch(`/api/admin/slots?date=${dateStr}`);
    const data = await res.json();
    const slots = data.slots || [];

    if (slots.length === 0) {
      adminSlotsList.innerHTML = `
        <div style="text-align: center; color: var(--color-text-muted); padding: 20px; background: #fff; border-radius: 12px; border: 1px dashed var(--color-border);">
          На этот день слотов еще нет.<br>Нажмите кнопки выше, чтобы добавить время приема.
        </div>
      `;
      return;
    }

    adminSlotsList.innerHTML = '';
    slots.forEach(slot => {
      const item = document.createElement('div');
      item.className = 'admin-card';
      item.style.display = 'flex';
      item.style.justifyContent = 'space-between';
      item.style.alignItems = 'center';
      item.style.margin = '0';

      const isBooked = slot.is_booked === 1;
      const isActive = slot.is_active === 1;

      item.innerHTML = `
        <div>
          <span style="font-size: 18px; font-weight: 700; color: var(--color-primary);">${slot.slot_time}</span>
          <div style="margin-top: 4px;">
            ${isBooked 
              ? '<span class="badge badge-pending">🔴 Занято клиентом</span>' 
              : (isActive ? '<span class="badge badge-confirmed">🟢 Свободно для записи</span>' : '<span class="badge badge-cancelled">Скрыто</span>')
            }
          </div>
        </div>
        <div style="display: flex; gap: 8px;">
          ${!isBooked ? `
            <button class="quick-slot-btn" style="background: ${isActive ? '#FEF2F2' : '#F0FDF4'}; color: ${isActive ? '#991B1B' : '#166534'}; border-color: transparent;" onclick="toggleSlot('${dateStr}', '${slot.slot_time}')">
              ${isActive ? 'Скрыть' : 'Открыть'}
            </button>
            <button class="quick-slot-btn" style="background: #FEE2E2; color: #991B1B; border: none;" onclick="deleteSlot(${slot.id})">
              ✕
            </button>
          ` : `
            <span style="font-size: 12px; color: var(--color-text-muted);">Запись оформлена</span>
          `}
        </div>
      `;
      adminSlotsList.appendChild(item);
    });

  } catch (err) {
    console.error('Ошибка загрузки слотов админа:', err);
  }
}

// Быстрое добавление слота
async function quickAddSlot(timeStr) {
  const dateStr = adminDatePicker.value;
  await fetch('/api/admin/slots', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slot_date: dateStr, slot_time: timeStr })
  });
  loadAdminSlots();
}

addCustomSlotBtn.addEventListener('click', () => {
  const timeStr = customTimeInput.value;
  if (timeStr) {
    quickAddSlot(timeStr);
  }
});

async function toggleSlot(dateStr, timeStr) {
  await fetch('/api/admin/slots', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slot_date: dateStr, slot_time: timeStr })
  });
  loadAdminSlots();
}

async function deleteSlot(slotId) {
  if (confirm('Удалить это окошко?')) {
    await fetch(`/api/admin/slots/${slotId}`, { method: 'DELETE' });
    loadAdminSlots();
  }
}

// Загрузка списка записей
async function loadAdminBookings() {
  adminBookingsList.innerHTML = '<div style="text-align: center; color: var(--color-text-muted); padding: 16px;">Загрузка записей...</div>';

  try {
    const res = await fetch('/api/admin/bookings');
    const data = await res.json();
    const bookings = data.bookings || [];

    if (bookings.length === 0) {
      adminBookingsList.innerHTML = `
        <div style="text-align: center; color: var(--color-text-muted); padding: 24px; background: #fff; border-radius: 12px;">
          Записей пока нет. Когда клиент запишется, заявка появится здесь и вам в Telegram придет уведомление.
        </div>
      `;
      return;
    }

    adminBookingsList.innerHTML = '';
    bookings.forEach(b => {
      const card = document.createElement('div');
      card.className = 'booking-card';

      let statusBadge = '<span class="badge badge-pending">Ожидает подтверждения</span>';
      if (b.status === 'confirmed') statusBadge = '<span class="badge badge-confirmed">Подтверждена</span>';
      if (b.status === 'cancelled') statusBadge = '<span class="badge badge-cancelled">Отменена</span>';

      const photoHtml = b.reference_photo 
        ? `
          <div style="margin-top: 10px;">
            <div style="font-size: 12px; color: var(--color-text-muted); margin-bottom: 4px;">📸 Референс от клиента (нажмите для зума):</div>
            <img src="/uploads/${b.reference_photo}" style="width: 80px; height: 80px; object-fit: cover; border-radius: 8px; cursor: pointer; border: 1px solid var(--color-border);" onclick="openLightbox('/uploads/${b.reference_photo}')">
          </div>
        ` 
        : '<div style="font-size: 12px; color: var(--color-text-muted); margin-top: 6px;">📷 Без фото референса</div>';

      const tgUser = (b.client_telegram || '').replace('@', '');

      card.innerHTML = `
        <div class="booking-header">
          <div>
            <div style="font-size: 16px; font-weight: 700; color: var(--color-text);">${b.client_name}</div>
            <div style="font-size: 13px; color: var(--color-primary); font-weight: 600;">${b.service_title} • ${b.service_price}</div>
          </div>
          <div>${statusBadge}</div>
        </div>

        <div style="font-size: 13px; color: var(--color-text); line-height: 1.6; margin-top: 6px;">
          <div>📅 <b>Дата:</b> ${b.slot_date} в <b>${b.slot_time}</b></div>
          <div>📞 <b>Телефон:</b> <a href="tel:${b.client_phone}" style="color: var(--color-primary); font-weight: 600;">${b.client_phone}</a></div>
          ${tgUser ? `<div>💬 <b>Telegram:</b> <a href="https://t.me/${tgUser}" target="_blank" style="color: #0284C7; font-weight: 600;">@${tgUser}</a></div>` : ''}
          ${b.client_comment ? `<div style="margin-top: 6px; background: #F8F9FA; padding: 8px 10px; border-radius: 6px; font-size: 12px; font-style: italic;">«${b.client_comment}»</div>` : ''}
        </div>

        ${photoHtml}

        <div class="client-actions">
          ${b.status !== 'confirmed' ? `<button class="btn-action btn-confirm" onclick="setBookingStatus(${b.id}, 'confirmed')">Подтвердить</button>` : ''}
          ${b.status !== 'cancelled' ? `<button class="btn-action btn-cancel" onclick="setBookingStatus(${b.id}, 'cancelled')">Отменить</button>` : ''}
          ${tgUser ? `<a href="https://t.me/${tgUser}" target="_blank" class="btn-action btn-tg">Написать в TG</a>` : ''}
        </div>
      `;

      adminBookingsList.appendChild(card);
    });

  } catch (err) {
    console.error('Ошибка загрузки записей:', err);
  }
}

async function setBookingStatus(bookingId, status) {
  try {
    await fetch(`/api/admin/bookings/${bookingId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    });
    loadAdminBookings();
  } catch (err) {
    alert('Ошибка смены статуса');
  }
}

// Lightbox
function openLightbox(src) {
  lightboxImg.src = src;
  lightbox.style.display = 'flex';
}

function closeLightbox() {
  lightbox.style.display = 'none';
}

// Запуск
document.addEventListener('DOMContentLoaded', () => {
  initDate();
  loadAdminSlots();
});
