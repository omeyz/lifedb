import Foundation

struct SummaryResponse: Decodable {
    let date: String
    let today: DayStats
    let spending: Spending
}

struct DayStats: Decodable {
    let steps: Double?
    let textsSent: Int?
    let textsReceived: Int?
    let emailsSent: Int?
    let emailsReceived: Int?
    let phoneCalls: Int?
    let talkMinutes: Double?

    var totalTexts: Int { (textsSent ?? 0) + (textsReceived ?? 0) }
    var totalEmails: Int { (emailsSent ?? 0) + (emailsReceived ?? 0) }
    var stepsInt: Int { Int(steps ?? 0) }
}

struct Spending: Decodable {
    let today: Double?
}
