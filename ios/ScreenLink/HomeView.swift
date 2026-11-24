import SwiftUI

struct HomeView: View {
    @EnvironmentObject var store: PCStore
    @State private var found: [FoundPC] = []
    @State private var scanning = false
    @State private var showAdd = false
    @State private var pinFor: FoundPC?
    @State private var open: SavedPC?

    var body: some View {
        NavigationStack {
            List {
                if !store.pcs.isEmpty {
                    Section("My PCs") {
                        ForEach(store.pcs) { pc in
                            Button { open = pc } label: {
                                HStack {
                                    Image(systemName: "desktopcomputer").foregroundStyle(.blue)
                                    VStack(alignment: .leading) {
                                        Text(pc.name).foregroundStyle(.primary)
                                        Text(pc.host).font(.caption).foregroundStyle(.secondary)
                                    }
                                    Spacer()
                                    Image(systemName: "chevron.right").foregroundStyle(.tertiary)
                                }
                            }
                        }
                        .onDelete { store.pcs.remove(atOffsets: $0) }
                    }
                }

                Section {
                    Button {
                        Task { await scan() }
                    } label: {
                        HStack {
                            Label(scanning ? "Looking for PCs…" : "Scan this network", systemImage: "wifi")
                            Spacer()
                            if scanning { ProgressView() }
                        }
                    }
                    .disabled(scanning)
                    ForEach(found.filter { f in !store.pcs.contains { $0.host == f.host } }) { f in
                        Button { pinFor = f } label: {
                            Label("\(f.name)  (\(f.host))", systemImage: "plus.circle")
                        }
                    }
                } header: {
                    Text("Find a PC")
                } footer: {
                    Text("Run ScreenLink on the PC first. The PC and this iPhone must be on the same Wi-Fi, or the PC joined to this iPhone's hotspot. No internet needed. If nothing shows the first time, allow Local Network and scan again.")
                }
            }
            .navigationTitle("ScreenLink")
            .toolbar {
                Button { showAdd = true } label: { Image(systemName: "plus") }
            }
            .sheet(isPresented: $showAdd) {
                AddPCView(host: "", name: "") { store.upsert($0); open = $0 }
            }
            .sheet(item: $pinFor) { f in
                AddPCView(host: f.host, name: f.name) { store.upsert($0); open = $0 }
            }
            .fullScreenCover(item: $open) { pc in
                ViewerView(pc: pc)
            }
            .task { if store.pcs.isEmpty { await scan() } }
        }
    }

    @MainActor
    private func scan() async {
        scanning = true
        found = []
        await Scanner.scan { f in
            if !found.contains(f) { found.append(f) }
        }
        scanning = false
    }
}

struct AddPCView: View {
    @Environment(\.dismiss) private var dismiss
    @State var host: String
    @State var name: String
    @State private var pin = ""
    var onSave: (SavedPC) -> Void

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("PC address, e.g. 192.168.1.20", text: $host)
                        .keyboardType(.numbersAndPunctuation)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    TextField("Name (optional)", text: $name)
                    TextField("PIN shown on the PC", text: $pin)
                        .keyboardType(.numberPad)
                }
            }
            .navigationTitle("Add PC")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Connect") {
                        let h = host.trimmingCharacters(in: .whitespaces)
                            .replacingOccurrences(of: "http://", with: "")
                            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
                        let pc = SavedPC(name: name.isEmpty ? h : name, host: h,
                                         pin: pin.trimmingCharacters(in: .whitespaces))
                        dismiss()
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { onSave(pc) }
                    }
                    .disabled(host.trimmingCharacters(in: .whitespaces).isEmpty || pin.isEmpty)
                }
            }
        }
    }
}
