import SwiftUI

@main
struct ScreenLinkApp: App {
    @StateObject private var store = PCStore()

    var body: some Scene {
        WindowGroup {
            HomeView()
                .environmentObject(store)
                .preferredColorScheme(.dark)
        }
    }
}

struct SavedPC: Codable, Identifiable, Equatable {
    var id = UUID()
    var name: String
    var host: String
    var pin: String

    var url: URL? {
        let h = host.contains(":") ? host : "\(host):8765"
        let k = pin.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? pin
        return URL(string: "http://\(h)/?k=\(k)")
    }
}

final class PCStore: ObservableObject {
    @Published var pcs: [SavedPC] = [] { didSet { save() } }
    private let key = "savedPCs"

    init() {
        if let d = UserDefaults.standard.data(forKey: key),
           let list = try? JSONDecoder().decode([SavedPC].self, from: d) {
            pcs = list
        }
    }

    private func save() {
        if let d = try? JSONEncoder().encode(pcs) { UserDefaults.standard.set(d, forKey: key) }
    }

    func upsert(_ pc: SavedPC) {
        if let i = pcs.firstIndex(where: { $0.host == pc.host }) {
            var p = pc; p.id = pcs[i].id; pcs[i] = p
        } else {
            pcs.insert(pc, at: 0)
        }
    }
}
