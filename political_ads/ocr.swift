import Foundation
import ImageIO
import Vision

for path in CommandLine.arguments.dropFirst() {
    do {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = ["en-US"]
        request.usesLanguageCorrection = false
        request.minimumTextHeight = 0.003
        try VNImageRequestHandler(url: URL(fileURLWithPath: path), options: [:])
            .perform([request])
        let lines: [[String: Any]] = (request.results ?? []).compactMap { observation in
            guard let text = observation.topCandidates(1).first else { return nil }
            let box = observation.boundingBox
            return [
                "text": text.string,
                "confidence": text.confidence,
                "bounds": [box.minX, box.minY, box.width, box.height],
            ]
        }
        let result: [String: Any] = [
            "path": path,
            "image_frame_count": CGImageSourceCreateWithURL(
                URL(fileURLWithPath: path) as CFURL, nil
            ).map { CGImageSourceGetCount($0) } ?? 0,
            "engine": "Apple Vision VNRecognizeTextRequest, accurate, en-US, no language correction",
            "coordinate_system": "normalized x,y,width,height; origin at image bottom-left",
            "lines": lines,
        ]
        let data = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
        print(String(decoding: data, as: UTF8.self))
    } catch {
        FileHandle.standardError.write(Data("\(path): \(error)\n".utf8))
        exit(1)
    }
}
