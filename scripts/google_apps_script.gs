function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('FloodGuard')
    .addItem('Run Status Check', 'runStatusCheck')
    .addToUi();
}

function runStatusCheck() {
  SpreadsheetApp.getActiveSpreadsheet().toast('FloodGuard script is active.', 'Status');
}
