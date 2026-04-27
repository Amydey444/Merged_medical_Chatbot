const PDFParser = require("pdf2json");
const fs = require("fs");

const pdfParser = new PDFParser(this, 1);

pdfParser.on("pdfParser_dataError", errData => {
    console.error(errData.parserError);
});

pdfParser.on("pdfParser_dataReady", pdfData => {
    fs.writeFileSync("parsed_pdf.txt", pdfParser.getRawTextContent(), "utf8");
    console.log("PDF parsed successfully. Text saved to parsed_pdf.txt");
});

pdfParser.loadPDF("_Modifications for AI Chatbot .pdf");