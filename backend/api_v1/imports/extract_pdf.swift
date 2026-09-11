import Foundation
import PDFKit
let url = URL(fileURLWithPath: CommandLine.arguments[1])
guard let doc = PDFDocument(url: url), !doc.isLocked, doc.pageCount <= 200 else {
    exit(1)
}
var text = ""
for i in 0..<doc.pageCount {
    text += (doc.page(at: i)?.string ?? "") + "\n"
    if text.utf8.count > 8_000_000 { exit(1) }
}
print(text)
