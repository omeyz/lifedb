import SwiftUI
import WidgetKit

struct ContentView: View {
    @State private var status: String = "Tap to test the Tailscale connection."
    @State private var loading = false

    var body: some View {
        VStack(spacing: 20) {
            Text("Life Widget")
                .font(.largeTitle).bold()

            Text("Long-press an empty spot on your home screen, tap +, and add Life Widget.")
                .font(.callout)
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)
                .padding(.horizontal)

            Button {
                Task { await runTest() }
            } label: {
                if loading {
                    ProgressView()
                } else {
                    Text("Test connection")
                }
            }
            .buttonStyle(.borderedProminent)
            .disabled(loading)

            Text(status)
                .font(.footnote)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)

            Button("Reload widgets") {
                WidgetCenter.shared.reloadAllTimelines()
            }
            .font(.footnote)

            Spacer()
        }
        .padding(.top, 40)
    }

    private func runTest() async {
        loading = true
        defer { loading = false }
        do {
            let s = try await LifeDataClient.fetchSummary()
            let steps = s.today.stepsInt
            let spend = s.spending.today ?? 0
            let texts = s.today.totalTexts
            status = "OK\nSteps: \(steps)  Spent: $\(String(format: "%.2f", abs(spend)))  Texts: \(texts)"
        } catch {
            status = "Error: \(error.localizedDescription)"
        }
    }
}

#Preview {
    ContentView()
}
