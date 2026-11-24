import Foundation

struct FoundPC: Identifiable, Hashable {
    var id: String { host }
    let host: String
    let name: String
}

/// Finds PCs running ScreenLink by asking every address of the local networks for /hello.
/// Plain HTTP to each address, so it also works on an iPhone hotspot with no internet.
enum Scanner {
    static func localPrefixes() -> [String] {
        var result: [String] = []
        var ifaddr: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&ifaddr) == 0, let first = ifaddr else { return [] }
        defer { freeifaddrs(ifaddr) }
        var ptr: UnsafeMutablePointer<ifaddrs>? = first
        while let p = ptr {
            let ifa = p.pointee
            ptr = ifa.ifa_next
            guard let addr = ifa.ifa_addr, addr.pointee.sa_family == UInt8(AF_INET) else { continue }
            let name = String(cString: ifa.ifa_name)
            guard name.hasPrefix("en") || name.hasPrefix("bridge") || name.hasPrefix("ap") else { continue }
            var host = [CChar](repeating: 0, count: Int(NI_MAXHOST))
            if getnameinfo(addr, socklen_t(addr.pointee.sa_len), &host, socklen_t(host.count), nil, 0, NI_NUMERICHOST) == 0 {
                let ip = String(cString: host)
                if ip.hasPrefix("169.254.") || ip.hasPrefix("127.") { continue }
                let parts = ip.split(separator: ".")
                if parts.count == 4 {
                    let prefix = parts[0...2].joined(separator: ".")
                    if !result.contains(prefix) { result.append(prefix) }
                }
            }
        }
        return result
    }

    static func probe(_ host: String, timeout: TimeInterval = 1.2) async -> FoundPC? {
        guard let url = URL(string: "http://\(host):8765/hello") else { return nil }
        var req = URLRequest(url: url)
        req.timeoutInterval = timeout
        let cfg = URLSessionConfiguration.ephemeral
        cfg.timeoutIntervalForRequest = timeout
        cfg.timeoutIntervalForResource = timeout
        cfg.waitsForConnectivity = false
        let session = URLSession(configuration: cfg)
        defer { session.finishTasksAndInvalidate() }
        guard let (data, resp) = try? await session.data(for: req),
              (resp as? HTTPURLResponse)?.statusCode == 200,
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              obj["app"] as? String == "screenlink" else { return nil }
        return FoundPC(host: host, name: obj["name"] as? String ?? host)
    }

    static func scan(onFound: @escaping @MainActor (FoundPC) -> Void) async {
        let hosts = localPrefixes().flatMap { pre in (1...254).map { "\(pre).\($0)" } }
        await withTaskGroup(of: FoundPC?.self) { group in
            var next = 0
            while next < min(48, hosts.count) {
                let h = hosts[next]
                group.addTask { await Scanner.probe(h) }
                next += 1
            }
            while let r = await group.next() {
                if let r { await onFound(r) }
                if next < hosts.count {
                    let h = hosts[next]
                    group.addTask { await Scanner.probe(h) }
                    next += 1
                }
            }
        }
    }
}
