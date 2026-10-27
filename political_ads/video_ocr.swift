import AVFoundation
import Foundation
import Vision

do {
    let asset = AVURLAsset(url: URL(fileURLWithPath: CommandLine.arguments[1]))
    let duration = CMTimeGetSeconds(asset.duration)
    guard duration.isFinite && duration > 0 && duration <= 300 else {
        throw NSError(domain: "VideoOCR", code: 1, userInfo: [
            NSLocalizedDescriptionKey: "Expected a complete video of at most five minutes",
        ])
    }
    let generator = AVAssetImageGenerator(asset: asset)
    generator.appliesPreferredTrackTransform = true
    generator.requestedTimeToleranceBefore = .zero
    generator.requestedTimeToleranceAfter = .zero
    let times = Array(stride(from: 0.0, to: duration, by: 1.0)) + [max(0, duration - 0.05)]
    var frames: [[String: Any]] = []
    for seconds in times {
        try autoreleasepool {
            var actual = CMTime.zero
            let image = try generator.copyCGImage(
                at: CMTime(seconds: seconds, preferredTimescale: 600), actualTime: &actual
            )
            let request = VNRecognizeTextRequest()
            request.recognitionLevel = .accurate
            request.recognitionLanguages = ["en-US"]
            request.usesLanguageCorrection = false
            request.minimumTextHeight = 0.003
            try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
            let lines: [[String: Any]] = (request.results ?? []).compactMap { observation in
                guard let text = observation.topCandidates(1).first else { return nil }
                let box = observation.boundingBox
                return [
                    "text": text.string, "confidence": text.confidence,
                    "bounds": [box.minX, box.minY, box.width, box.height],
                ]
            }
            frames.append(["seconds": CMTimeGetSeconds(actual), "lines": lines])
        }
    }
    let result: [String: Any] = [
        "duration_seconds": duration, "sample_interval_seconds": 1,
        "engine": "Apple Vision accurate en-US, no language correction; AVFoundation frames",
        "coordinate_system": "normalized x,y,width,height; origin at image bottom-left",
        "frames": frames,
    ]
    let data = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
    print(String(decoding: data, as: UTF8.self))
} catch {
    FileHandle.standardError.write(Data("\(error)\n".utf8))
    exit(1)
}
