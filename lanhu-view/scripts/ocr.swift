#!/usr/bin/env swift
// macOS Vision OCR — 提取图片中的文字
// 用法: swift ocr.swift <image_path>

import Vision
import AppKit
import Foundation

guard CommandLine.arguments.count > 1 else {
    fputs("用法: swift ocr.swift <image_path>\n", stderr)
    exit(1)
}

let imagePath = CommandLine.arguments[1]
guard let image = NSImage(contentsOfFile: imagePath),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    fputs("无法加载图片: \(imagePath)\n", stderr)
    exit(1)
}

let request = VNRecognizeTextRequest()
request.recognitionLanguages = ["zh-Hans", "zh-Hant", "en-US"]
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
try? handler.perform([request])

let results = request.results ?? []
let lines = results.compactMap { $0.topCandidates(1).first?.string }
print(lines.joined(separator: "\n"))
