import SwiftUI
import WebKit

struct ViewerView: View {
    let pc: SavedPC
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack(alignment: .topLeading) {
            Color.black.ignoresSafeArea()
            if let url = pc.url {
                WebView(url: url).ignoresSafeArea()
            }
            Button { dismiss() } label: {
                Image(systemName: "xmark")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundStyle(.white)
                    .frame(width: 32, height: 32)
                    .background(.black.opacity(0.55), in: Circle())
            }
            .padding(.leading, 10)
            .padding(.top, 6)
        }
        .statusBarHidden(true)
        .persistentSystemOverlays(.hidden)
        .onAppear { UIApplication.shared.isIdleTimerDisabled = true }
        .onDisappear { UIApplication.shared.isIdleTimerDisabled = false }
    }
}

struct WebView: UIViewRepresentable {
    let url: URL

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> WKWebView {
        let cfg = WKWebViewConfiguration()
        cfg.allowsInlineMediaPlayback = true
        let wv = WKWebView(frame: .zero, configuration: cfg)
        wv.isOpaque = false
        wv.backgroundColor = .black
        wv.scrollView.backgroundColor = .black
        wv.scrollView.isScrollEnabled = false
        wv.scrollView.bounces = false
        wv.scrollView.contentInsetAdjustmentBehavior = .never
        wv.scrollView.pinchGestureRecognizer?.isEnabled = false
        wv.allowsLinkPreview = false
        wv.navigationDelegate = context.coordinator
        wv.load(URLRequest(url: url))
        context.coordinator.url = url
        return wv
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKNavigationDelegate {
        var url: URL?

        // The PC was not reachable: show a simple page and retry every few seconds.
        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            let html = """
            <html><head><meta name=viewport content='width=device-width,initial-scale=1'></head>
            <body style='background:#000;color:#ddd;font:17px -apple-system;display:flex;height:100vh;align-items:center;justify-content:center;text-align:center;padding:24px;box-sizing:border-box'>
            <div>Can't reach the PC.<br><br><span style='color:#888;font-size:14px'>Check ScreenLink is open on the PC and both are on the same Wi-Fi or hotspot. Trying again…</span></div></body></html>
            """
            webView.loadHTMLString(html, baseURL: nil)
            DispatchQueue.main.asyncAfter(deadline: .now() + 3) { [weak webView] in
                if let u = self.url { webView?.load(URLRequest(url: u)) }
            }
        }

        func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
            if let u = url { webView.load(URLRequest(url: u)) }
        }
    }
}
