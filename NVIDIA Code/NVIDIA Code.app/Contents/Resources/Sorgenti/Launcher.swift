import AppKit
import Foundation

final class Launcher: NSObject, NSApplicationDelegate {
    private var launched = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) { [weak self] in
            self?.launch(project: nil)
        }
    }

    func application(_ sender: NSApplication, openFiles filenames: [String]) {
        launch(project: filenames.first.map { URL(fileURLWithPath: $0) })
        sender.reply(toOpenOrPrint: .success)
    }

    private func shellQuote(_ value: String) -> String {
        return "'" + value.replacingOccurrences(of: "'", with: "'\\''") + "'"
    }

    private func showError(_ message: String) {
        let alert = NSAlert()
        alert.messageText = "Non riesco ad avviare NVIDIA Code"
        alert.informativeText = message
        alert.addButton(withTitle: "OK")
        NSApp.activate(ignoringOtherApps: true)
        alert.runModal()
        NSApp.terminate(nil)
    }

    private func launch(project: URL?) {
        guard !launched else { return }
        launched = true
        let appURL = Bundle.main.bundleURL
        let rootURL = appURL.deletingLastPathComponent()
        let launcher = appURL.appendingPathComponent("Contents/Resources/Avvia.command")
        var projectURL = project ?? rootURL.appendingPathComponent("Progetti", isDirectory: true)
        var directory: ObjCBool = false
        if FileManager.default.fileExists(atPath: projectURL.path, isDirectory: &directory), !directory.boolValue {
            projectURL.deleteLastPathComponent()
        }
        let temporaryFolder = FileManager.default.temporaryDirectory
            .appendingPathComponent("nvidia-code-" + UUID().uuidString, isDirectory: true)
        do {
            try FileManager.default.createDirectory(at: temporaryFolder, withIntermediateDirectories: false,
                                                    attributes: [.posixPermissions: 0o700])
            let commandURL = temporaryFolder.appendingPathComponent("Avvia-NVIDIA-Code.command")
            let command = """
            #!/bin/zsh
            temporary_folder="${0:A:h}"
            /bin/rm -f -- "$0"
            /bin/rmdir "$temporary_folder" 2>/dev/null
            exec /bin/zsh \(shellQuote(launcher.path)) \(shellQuote(projectURL.path))

            """
            try command.write(to: commandURL, atomically: true, encoding: .utf8)
            try FileManager.default.setAttributes([.posixPermissions: 0o700], ofItemAtPath: commandURL.path)
            guard let terminal = NSWorkspace.shared.urlForApplication(withBundleIdentifier: "com.apple.Terminal") else {
                try? FileManager.default.removeItem(at: temporaryFolder)
                showError("Terminale non è disponibile su questo Mac.")
                return
            }
            let configuration = NSWorkspace.OpenConfiguration()
            configuration.activates = true
            NSWorkspace.shared.open([commandURL], withApplicationAt: terminal, configuration: configuration) { [weak self] _, error in
                DispatchQueue.main.async {
                    if let error = error {
                        try? FileManager.default.removeItem(at: temporaryFolder)
                        self?.showError(error.localizedDescription)
                    } else {
                        NSApp.terminate(nil)
                    }
                }
            }
        } catch {
            try? FileManager.default.removeItem(at: temporaryFolder)
            showError(error.localizedDescription)
        }
    }
}

if CommandLine.arguments.contains("--verifica") {
    let resource = Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/Avvia.command")
    guard FileManager.default.isExecutableFile(atPath: resource.path) else {
        fputs("Launcher non trovato nel pacchetto app.\n", stderr)
        exit(1)
    }
    print("APP_BUNDLE_OK")
    exit(0)
}

let application = NSApplication.shared
let delegate = Launcher()
application.delegate = delegate
application.setActivationPolicy(.accessory)
application.run()
