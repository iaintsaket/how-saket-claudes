// Google Apps Script — paste this into https://script.google.com
// Then: Deploy > New deployment > Web app > Execute as Me > Anyone can access > Deploy
// Copy the web app URL into ~/.claude/interview-tracker-config.json

var SHEET_NAME = "IMock Interview Progress Tracker";
var HEADERS = [
  "Date", "Mode", "Questions Asked", "Score (/10)", "Verdict",
  "What Went Well", "What Went Wrong", "Topics to Brush Up"
];

function doPost(e) {
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName(SHEET_NAME);

    // Create sheet with headers on first run
    if (!sheet) {
      sheet = ss.insertSheet(SHEET_NAME);
      sheet.appendRow(HEADERS);
      formatHeaders(sheet);
    }

    var data = JSON.parse(e.postData.contents);

    sheet.appendRow([
      data.date        || "",
      data.mode        || "",
      data.questions   || "",
      data.score       || "",
      data.verdict     || "",
      data.positives   || "",
      data.negatives   || "",
      data.topics_to_brush_up || ""
    ]);

    // Colour-code the verdict cell
    var lastRow = sheet.getLastRow();
    var verdictCell = sheet.getRange(lastRow, 5);
    var verdict = (data.verdict || "").toLowerCase();
    if (verdict.includes("strong hire"))       verdictCell.setBackground("#00c851");
    else if (verdict.includes("hire"))         verdictCell.setBackground("#a8f0c6");
    else if (verdict.includes("strong no"))    verdictCell.setBackground("#ff4444");
    else if (verdict.includes("no hire"))      verdictCell.setBackground("#ffbb33");

    // Score cell: red < 5, orange 5-6, green >= 7
    var scoreCell = sheet.getRange(lastRow, 4);
    var score = parseFloat(data.score) || 0;
    if (score < 5)       scoreCell.setBackground("#ff4444");
    else if (score < 7)  scoreCell.setBackground("#ffbb33");
    else                 scoreCell.setBackground("#a8f0c6");

    return ContentService
      .createTextOutput(JSON.stringify({ status: "success", row: lastRow }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ status: "error", message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function formatHeaders(sheet) {
  var headerRange = sheet.getRange(1, 1, 1, HEADERS.length);
  headerRange.setBackground("#1a73e8");
  headerRange.setFontColor("#ffffff");
  headerRange.setFontWeight("bold");
  sheet.setFrozenRows(1);
  sheet.setColumnWidth(1, 100);  // Date
  sheet.setColumnWidth(2, 60);   // Mode
  sheet.setColumnWidth(3, 280);  // Questions
  sheet.setColumnWidth(4, 80);   // Score
  sheet.setColumnWidth(5, 120);  // Verdict
  sheet.setColumnWidth(6, 280);  // Positives
  sheet.setColumnWidth(7, 320);  // Negatives
  sheet.setColumnWidth(8, 280);  // Topics
}

// Run this once manually to test without POST
function testInsert() {
  var fakeEvent = {
    postData: {
      contents: JSON.stringify({
        date: "2026-04-23",
        mode: "DSA",
        questions: "Sliding Window - Fraud Detection, Graph - Drone Routing",
        score: 6,
        verdict: "No Hire",
        positives: "Stated complexity upfront, clean variable names",
        negatives: "Bug on duplicate input, skipped edge cases, no dry run on example",
        topics_to_brush_up: "Sliding Window, BFS on weighted graphs"
      })
    }
  };
  doPost(fakeEvent);
}
