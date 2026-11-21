import WidgetKit
import SwiftUI

struct LifeEntry: TimelineEntry {
    let date: Date
    let stats: SummaryResponse?
    let error: String?
}

struct LifeProvider: TimelineProvider {
    func placeholder(in context: Context) -> LifeEntry {
        LifeEntry(date: Date(), stats: nil, error: nil)
    }

    func getSnapshot(in context: Context, completion: @escaping (LifeEntry) -> Void) {
        Task {
            let entry = await fetchEntry()
            completion(entry)
        }
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<LifeEntry>) -> Void) {
        Task {
            let entry = await fetchEntry()
            // Refresh every 30 min → ~48 reloads/day, comfortably under iOS's budget.
            let next = Date().addingTimeInterval(30 * 60)
            completion(Timeline(entries: [entry], policy: .after(next)))
        }
    }

    private func fetchEntry() async -> LifeEntry {
        do {
            let s = try await LifeDataClient.fetchSummary()
            return LifeEntry(date: Date(), stats: s, error: nil)
        } catch {
            return LifeEntry(date: Date(), stats: nil, error: error.localizedDescription)
        }
    }
}

struct StatCell: View {
    let label: String
    let value: String
    let icon: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.caption2)
                Text(label)
                    .font(.caption2)
            }
            .foregroundStyle(.secondary)

            Text(value)
                .font(.title3)
                .fontWeight(.semibold)
                .lineLimit(1)
                .minimumScaleFactor(0.6)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct LifeWidgetEntryView: View {
    @Environment(\.widgetFamily) var family
    let entry: LifeEntry

    var body: some View {
        switch family {
        case .accessoryRectangular:
            rectangularBody
        default:
            mediumBody
        }
    }

    private var rectangularBody: some View {
        VStack(alignment: .leading, spacing: 1) {
            if let s = entry.stats {
                let t = s.period
                Text("7d · \(formatInt(t.stepsInt)) steps").fontWeight(.semibold)
                Text("\(formatMoney(s.spending.periodTotal ?? 0)) · \(t.totalTexts) msgs")
                Text("\(t.phoneCalls ?? 0) calls · \(t.totalEmails) emails")
                    .foregroundStyle(.secondary)
            } else {
                Text("Omar's Database").fontWeight(.semibold)
                Text(entry.error.map { "⚠︎ \($0)" } ?? "Loading…")
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
        }
        .font(.system(size: 14))
        .minimumScaleFactor(0.7)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .widgetAccentable()
    }

    private var mediumBody: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Last 7 Days")
                    .font(.caption).fontWeight(.semibold)
                    .foregroundStyle(.secondary)
                Spacer()
                Text(updatedLabel)
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }

            if let s = entry.stats {
                let t = s.period
                HStack(alignment: .top, spacing: 8) {
                    StatCell(label: "Steps", value: formatInt(t.stepsInt), icon: "figure.walk")
                    StatCell(label: "Distance", value: formatDistance(t.distanceKm ?? 0), icon: "map.fill")
                    StatCell(label: "Spent", value: formatMoney(s.spending.periodTotal ?? 0), icon: "creditcard.fill")
                }
                HStack(alignment: .top, spacing: 8) {
                    StatCell(label: "Texts", value: "\(t.totalTexts)", icon: "message.fill")
                    StatCell(label: "Calls", value: callsLabel(t), icon: "phone.fill")
                    StatCell(label: "Emails", value: "\(t.totalEmails)", icon: "envelope.fill")
                }
            } else if let err = entry.error {
                Spacer()
                Text("⚠︎ \(err)")
                    .font(.caption)
                    .foregroundStyle(.red)
                    .lineLimit(2)
                Spacer()
            } else {
                Spacer()
                Text("Loading…")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
            }
        }
    }

    private var updatedLabel: String {
        let fmt = DateFormatter()
        fmt.dateFormat = "h:mm a"
        return fmt.string(from: entry.date)
    }

    private func formatInt(_ n: Int) -> String {
        if n >= 10_000 { return String(format: "%.1fk", Double(n) / 1000) }
        if n >= 1000 { return "\(n / 1000),\(String(format: "%03d", n % 1000))" }
        return "\(n)"
    }

    private func formatDistance(_ km: Double) -> String {
        let miles = km * 0.621371
        if miles >= 10 { return String(format: "%.0fmi", miles) }
        return String(format: "%.1fmi", miles)
    }

    private func formatMoney(_ v: Double) -> String {
        let a = Swift.abs(v)
        if a >= 1000 { return String(format: "$%.1fk", a / 1000) }
        if a == 0 { return "$0" }
        return String(format: "$%.0f", a)
    }

    private func callsLabel(_ t: DayStats) -> String {
        let count = t.phoneCalls ?? 0
        let mins = Int((t.talkMinutes ?? 0).rounded())
        if count == 0 { return "0" }
        if mins == 0 { return "\(count)" }
        return "\(count) · \(mins)m"
    }
}

struct LifeWidget: Widget {
    let kind: String = "LifeWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: LifeProvider()) { entry in
            if #available(iOS 17.0, *) {
                LifeWidgetEntryView(entry: entry)
                    .containerBackground(.fill.tertiary, for: .widget)
            } else {
                LifeWidgetEntryView(entry: entry)
                    .padding()
            }
        }
        .configurationDisplayName("Omar's Database")
        .description("Last 7 days: steps, spending, texts, calls, emails.")
        .supportedFamilies([.systemMedium, .accessoryRectangular])
    }
}

#Preview(as: .systemMedium) {
    LifeWidget()
} timeline: {
    LifeEntry(
        date: .now,
        stats: SummaryResponse(
            date: "2026-04-21",
            today: DayStats(
                steps: 8000,
                distanceKm: 6.0,
                textsSent: 10,
                textsReceived: 20,
                emailsSent: 2,
                emailsReceived: 30,
                phoneCalls: 3,
                talkMinutes: 15
            ),
            period: DayStats(
                steps: 50000,
                distanceKm: 40.0,
                textsSent: 100,
                textsReceived: 200,
                emailsSent: 10,
                emailsReceived: 150,
                phoneCalls: 20,
                talkMinutes: 60
            ),
            spending: Spending(today: -25.00, periodTotal: -300.00)
        ),
        error: nil
    )
    LifeEntry(date: .now, stats: nil, error: "Network offline")
}
