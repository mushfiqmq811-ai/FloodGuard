// FloodGuard BD - Google Apps Script notification bridge
// Web app: Execute as Me, Who has access: Anyone.
// Email uses the owner's Gmail account. WhatsApp uses Meta WhatsApp Cloud API
// credentials stored in Script Properties (never hard-code secrets in this file).

function doGet() {
  return ContentService
    .createTextOutput(JSON.stringify({ok:true,service:'FloodGuard BD Notification Service'}))
    .setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents || '{}');
    const action = String(data.action || '').trim();

    if (action === 'send_email') return sendEmail_(data);
    if (action === 'send_whatsapp') return sendWhatsApp_(data);

    throw new Error('Invalid action');
  } catch (err) {
    return json_({ok:false,error:String(err)});
  }
}

function sendEmail_(data) {
  const to = String(data.to || '').trim();
  const subject = String(data.subject || 'FloodGuard BD Alert').trim();
  const body = String(data.body || '').trim();
  if (!to) throw new Error('Recipient email is required');
  if (!body) throw new Error('Email body is required');

  GmailApp.sendEmail(to, subject, body);
  return json_({ok:true,message:'Email sent successfully'});
}

function sendWhatsApp_(data) {
  const to = normalizePhone_(String(data.to || '').trim());
  const body = String(data.body || '').trim();
  if (!to) throw new Error('WhatsApp number is required');
  if (!body) throw new Error('WhatsApp body is required');

  const props = PropertiesService.getScriptProperties();
  const token = props.getProperty('WHATSAPP_ACCESS_TOKEN');
  const phoneNumberId = props.getProperty('WHATSAPP_PHONE_NUMBER_ID');
  if (!token || !phoneNumberId) {
    throw new Error('WhatsApp Cloud API is not configured in Script Properties');
  }

  const url = 'https://graph.facebook.com/v23.0/' + phoneNumberId + '/messages';
  const payload = {
    messaging_product: 'whatsapp',
    recipient_type: 'individual',
    to: to,
    type: 'text',
    text: { preview_url: false, body: body }
  };

  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + token },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });

  const code = response.getResponseCode();
  const text = response.getContentText();
  if (code < 200 || code >= 300) {
    throw new Error('WhatsApp API ' + code + ': ' + text.slice(0, 500));
  }
  return json_({ok:true,message:'WhatsApp sent successfully',response:text});
}

function normalizePhone_(phone) {
  // Keep digits and an optional leading +. Meta expects international E.164 style.
  return phone.replace(/[^0-9+]/g, '').replace(/^00/, '+').replace(/^\+/, '');
}

function json_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function sendTestEmail() {
  const to = 'YOUR_GMAIL@gmail.com';
  GmailApp.sendEmail(to, 'FloodGuard BD — Test Alert', 'Your FloodGuard email bridge is working.');
}
