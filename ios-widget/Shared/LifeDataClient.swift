import Foundation

enum LifeDataError: LocalizedError {
    case badStatus(Int)
    case badURL

    var errorDescription: String? {
        switch self {
        case .badStatus(let code): return "HTTP \(code)"
        case .badURL: return "Bad URL"
        }
    }
}

enum LifeDataClient {
    // The address of your LifeDB dashboard (scripts/dashboard.py), reachable from the phone.
    // A private network such as Tailscale works well; see ios-widget/README.md.
    static let baseURL = URL(string: "http://lifedb.example:8080")!

    static func fetchSummary() async throws -> SummaryResponse {
        let url = baseURL.appendingPathComponent("api/summary")
        var req = URLRequest(url: url)
        req.timeoutInterval = 10
        req.cachePolicy = .reloadIgnoringLocalCacheData

        let (data, response) = try await URLSession.shared.data(for: req)
        guard let http = response as? HTTPURLResponse else {
            throw LifeDataError.badStatus(-1)
        }
        guard (200..<300).contains(http.statusCode) else {
            throw LifeDataError.badStatus(http.statusCode)
        }

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(SummaryResponse.self, from: data)
    }
}
