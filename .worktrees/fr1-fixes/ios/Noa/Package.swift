    // swift-tools-version: 6.0
// The swift-tools-version declares the minimum version of Swift required to build this package.

import PackageDescription

let package = Package(
    name: "Noa",
    platforms: [
        .iOS(.v17),
        .macOS(.v14),
    ],
    products: [
        .library(
            name: "Noa",
            targets: ["Noa"]
        ),
    ],
    targets: [
        .target(
            name: "Noa",
            path: "Sources/Noa"
        ),
        .testTarget(
            name: "NaoTests",
            dependencies: ["Noa"],
            path: "Tests/NaoTests"
        ),
    ]
)
