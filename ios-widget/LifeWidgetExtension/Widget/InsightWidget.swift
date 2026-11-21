import WidgetKit
import SwiftUI

struct InsightEntry: TimelineEntry {
    let date: Date
    let insight: InsightResponse?
    let error: String?
}

struct InsightProvider: TimelineProvider {
    func placeholder(in context: Context) -> InsightEntry {
        InsightEntry(date: Date(), insight: nil, error: nil)
    }

    func getSnapshot(in context: Context, completion: @escaping (InsightEntry) -> Void) {
        Task {
            let entry = await fetchEntry()
            completion(entry)
        }
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<InsightEntry>) -> Void) {
        Task {
            let entry = await fetchEntry()
            // Refresh every 30 min. The server generates new insights every 90 min,
            // so the widget will show fresh content 1-2 refreshes after generation.
            let next = Date().addingTimeInterval(30 * 60)
            completion(Timeline(entries: [entry], policy: .after(next)))
        }
    }

    private func fetchEntry() async -> InsightEntry {
        do {
            let i = try await LifeDataClient.fetchInsight()
            return InsightEntry(date: Date(), insight: i, error: nil)
        } catch {
            return InsightEntry(date: Date(), insight: nil, error: error.localizedDescription)
        }
    }
}

struct InsightWidgetEntryView: View {
    @Environment(\.widgetFamily) var family
    let entry: InsightEntry

    var body: some View {
        switch family {
        case .accessoryRectangular:
            rectangularBody
        case .accessoryInline:
            inlineBody
        default:
            mediumBody
        }
    }

    private var rectangularBody: some View {
        VStack(alignment: .leading, spacing: 0) {
            if let msg = entry.insight?.message, !msg.isEmpty {
                Text(msg)
                    .fontWeight(.bold)
                    .multilineTextAlignment(.leading)
                    .lineLimit(4)
                    .minimumScaleFactor(0.6)
            } else if let err = entry.error {
                Text("⚠︎ \(err)").fontWeight(.bold).lineLimit(3)
            } else {
                Text("No insight yet.").fontWeight(.bold)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .widgetAccentable()
    }

    private var inlineBody: some View {
        Text(entry.insight?.message ?? "No insight yet.")
            .lineLimit(1)
    }

    private var mediumBody: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Insight")
                    .font(.caption).fontWeight(.semibold)
                    .foregroundStyle(.secondary)
                Spacer()
                Text(generatedLabel)
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }

            if let msg = entry.insight?.longMessage ?? entry.insight?.message, !msg.isEmpty {
                Text(msg)
                    .font(.footnote)
                    .foregroundStyle(.primary)
                    .multilineTextAlignment(.leading)
                    .lineLimit(8)
                    .minimumScaleFactor(0.75)
                    .frame(maxHeight: .infinity, alignment: .topLeading)
            } else if let err = entry.error {
                Spacer()
                Text("⚠︎ \(err)")
                    .font(.caption)
                    .foregroundStyle(.red)
                    .lineLimit(3)
                Spacer()
            } else {
                Spacer()
                Text("No insight yet.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
            }
        }
    }

    private var generatedLabel: String {
        guard let at = entry.insight?.generatedAt else { return "" }
        // API format: "2026-04-21 07:56:35" — display just HH:MM
        let parts = at.split(separator: " ")
        guard parts.count >= 2 else { return "" }
        let time = String(parts[1])
        return String(time.prefix(5))
    }
}

struct InsightWidget: Widget {
    let kind: String = "InsightWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: InsightProvider()) { entry in
            if #available(iOS 17.0, *) {
                InsightWidgetEntryView(entry: entry)
                    .containerBackground(.fill.tertiary, for: .widget)
            } else {
                InsightWidgetEntryView(entry: entry)
                    .padding()
            }
        }
        .configurationDisplayName("Omar's Database — Insight")
        .description("A short, directive read on your day from the calendar.")
        .supportedFamilies([.systemMedium, .accessoryRectangular, .accessoryInline])
    }
}

#Preview(as: .systemMedium) {
    InsightWidget()
} timeline: {
    InsightEntry(
        date: .now,
        insight: InsightResponse(
            message: "Get to sleep now so you are sharp for the 10am call.",
            longMessage: "It is past 1am and your first commitment is the 10am call, so close the laptop and rest. Two of your afternoon blocks overlap, so decide in the morning which one needs you in the room.",
            generatedAt: "2026-04-21 08:30:00",
            model: "claude-opus-4-7"
        ),
        error: nil
    )
    InsightEntry(date: .now, insight: nil, error: "Network offline")
}
