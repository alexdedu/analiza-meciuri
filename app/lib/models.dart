/// Modelele de date care oglindesc structura din predictions.json.
///
/// Fisierul e generat de research/predict.py si este inclus ca asset,
/// deci aplicatia porneste instant si functioneaza complet offline.
library;

class TeamContext {
  const TeamContext({
    required this.form,
    required this.goalsForAvg,
    required this.goalsAgainstAvg,
    required this.shotsOnTargetAvg,
    required this.matchesAnalysed,
  });

  /// Rezultate recente ca litere: V (victorie), E (egal), I (infrangere).
  /// Ultimul element este cel mai recent meci.
  final List<String> form;
  final double? goalsForAvg;
  final double? goalsAgainstAvg;
  final double? shotsOnTargetAvg;
  final int matchesAnalysed;

  factory TeamContext.fromJson(Map<String, dynamic> json) => TeamContext(
        form: (json['form'] as List<dynamic>? ?? []).cast<String>(),
        goalsForAvg: (json['goals_for_avg'] as num?)?.toDouble(),
        goalsAgainstAvg: (json['goals_against_avg'] as num?)?.toDouble(),
        shotsOnTargetAvg: (json['shots_on_target_avg'] as num?)?.toDouble(),
        matchesAnalysed: (json['matches_analysed'] as num?)?.toInt() ?? 0,
      );
}

class HeadToHead {
  const HeadToHead({
    required this.date,
    required this.home,
    required this.away,
    required this.score,
  });

  final String date;
  final String home;
  final String away;
  final String score;

  factory HeadToHead.fromJson(Map<String, dynamic> json) => HeadToHead(
        date: json['date'] as String,
        home: json['home'] as String,
        away: json['away'] as String,
        score: json['score'] as String,
      );
}

class ScoreLine {
  const ScoreLine(this.score, this.probability);

  final String score;
  final double probability;

  factory ScoreLine.fromJson(Map<String, dynamic> json) =>
      ScoreLine(json['score'] as String, (json['p'] as num).toDouble());
}

/// Cat de multe meciuri stau in spatele estimarii. O echipa nou promovata
/// are putine meciuri in liga curenta, deci forta ei e prost estimata.
enum Confidence {
  ridicata,
  medie,
  scazuta;

  static Confidence parse(String? value) => switch (value) {
        'ridicata' => Confidence.ridicata,
        'medie' => Confidence.medie,
        _ => Confidence.scazuta,
      };

  String get label => switch (this) {
        Confidence.ridicata => 'Date solide',
        Confidence.medie => 'Date partiale',
        Confidence.scazuta => 'Date putine',
      };
}

/// O linie de pariu pe contori: "peste 9.5 cornere" si probabilitatea ei.
class CountLine {
  const CountLine({required this.line, required this.over, this.under});

  final double line;
  final double over;

  /// Lipseste la liniile pe echipa, unde afisam doar "peste".
  final double? under;

  factory CountLine.fromJson(Map<String, dynamic> json) => CountLine(
        line: (json['line'] as num).toDouble(),
        over: (json['over'] as num).toDouble(),
        under: (json['under'] as num?)?.toDouble(),
      );
}

/// Arbitrul delegat si cat de mult isi pune amprenta pe cartonase.
class RefereeInfo {
  const RefereeInfo({
    required this.name,
    required this.factor,
    required this.matches,
  });

  final String name;

  /// Cat da fata de asteptari, deja tras spre 1 pentru arbitrii cu putine
  /// meciuri: 1.12 inseamna cu 12% mai multe cartonase decat media.
  final double factor;
  final int matches;

  static RefereeInfo? fromJson(Map<String, dynamic>? json) {
    if (json == null) return null;
    return RefereeInfo(
      name: json['name'] as String,
      factor: (json['factor'] as num).toDouble(),
      matches: (json['matches'] as num?)?.toInt() ?? 0,
    );
  }
}

/// Cornere sau cartonase pentru un meci: asteptari si linii.
class CountsMarket {
  const CountsMarket({
    required this.expectedHome,
    required this.expectedAway,
    required this.expectedTotal,
    required this.total,
    required this.home,
    required this.away,
    required this.winner,
    required this.sample,
    this.referee,
  });

  final double expectedHome;
  final double expectedAway;
  final double expectedTotal;
  final List<CountLine> total;
  final List<CountLine> home;
  final List<CountLine> away;

  /// Cine produce mai multe (doar la cornere): p_home, p_draw, p_away.
  final Map<String, double>? winner;

  /// Cate meciuri au stat la baza fitului.
  final int sample;

  /// Arbitrul delegat (doar la cartonase, si doar dupa ce a fost anuntat).
  final RefereeInfo? referee;

  static List<CountLine> _linii(dynamic brut) =>
      ((brut as List<dynamic>?) ?? [])
          .map((e) => CountLine.fromJson(e as Map<String, dynamic>))
          .toList();

  factory CountsMarket.fromJson(Map<String, dynamic> json) {
    final asteptat = json['expected'] as Map<String, dynamic>;
    final castigator = json['winner'] as Map<String, dynamic>?;
    return CountsMarket(
      expectedHome: (asteptat['home'] as num).toDouble(),
      expectedAway: (asteptat['away'] as num).toDouble(),
      expectedTotal: (asteptat['total'] as num).toDouble(),
      total: _linii(json['total']),
      home: _linii(json['home']),
      away: _linii(json['away']),
      winner: castigator?.map((k, v) => MapEntry(k, (v as num).toDouble())),
      sample: (json['sample'] as num?)?.toInt() ?? 0,
      referee: RefereeInfo.fromJson(json['referee'] as Map<String, dynamic>?),
    );
  }
}

/// Pietele in plus fata de rezultat si goluri.
///
/// Lipsesc la meciurile pentru care sursa nu are datele: Romania, celelalte 18
/// tari din feedul suplimentar, cupele europene si nationalele.
class ExtraMarkets {
  const ExtraMarkets({required this.corners, required this.cards});

  final CountsMarket? corners;
  final CountsMarket? cards;

  bool get isEmpty => corners == null && cards == null;

  static ExtraMarkets? fromJson(Map<String, dynamic>? json) {
    if (json == null) return null;
    final e = ExtraMarkets(
      corners: json['corners'] == null
          ? null
          : CountsMarket.fromJson(json['corners'] as Map<String, dynamic>),
      cards: json['cards'] == null
          ? null
          : CountsMarket.fromJson(json['cards'] as Map<String, dynamic>),
    );
    return e.isEmpty ? null : e;
  }
}

class MatchPrediction {
  const MatchPrediction({
    required this.id,
    required this.league,
    required this.leagueName,
    required this.date,
    required this.time,
    required this.home,
    required this.away,
    required this.probabilities,
    required this.expectedGoalsHome,
    required this.expectedGoalsAway,
    required this.confidence,
    required this.homeMatches,
    required this.awayMatches,
    required this.topScores,
    required this.referenceOdds,
    required this.homeContext,
    required this.awayContext,
    required this.headToHead,
    required this.explanation,
    this.extraMarkets,
  });

  final String id;
  final String league;
  final String leagueName;
  final DateTime date;
  final String time;
  final String home;
  final String away;

  /// Chei: p_home, p_draw, p_away, p_over25, p_under25, p_btts, p_no_btts
  final Map<String, double> probabilities;
  final double expectedGoalsHome;
  final double expectedGoalsAway;
  final Confidence confidence;
  final int homeMatches;
  final int awayMatches;
  final List<ScoreLine> topScores;
  final Map<String, double> referenceOdds;
  final TeamContext homeContext;
  final TeamContext awayContext;
  final List<HeadToHead> headToHead;
  final String explanation;

  /// Cornere si cartonase, unde sursa le are.
  final ExtraMarkets? extraMarkets;

  double p(String key) => probabilities[key] ?? 0;

  factory MatchPrediction.fromJson(Map<String, dynamic> json) {
    final context = json['context'] as Map<String, dynamic>;
    final sample = json['sample'] as Map<String, dynamic>? ?? const {};
    return MatchPrediction(
      id: json['id'] as String,
      league: json['league'] as String,
      leagueName: json['league_name'] as String,
      date: DateTime.parse(json['date'] as String),
      time: (json['time'] as String?) ?? '',
      home: json['home'] as String,
      away: json['away'] as String,
      probabilities: (json['probs'] as Map<String, dynamic>)
          .map((k, v) => MapEntry(k, (v as num).toDouble())),
      expectedGoalsHome:
          ((json['expected_goals'] as Map<String, dynamic>)['home'] as num).toDouble(),
      expectedGoalsAway:
          ((json['expected_goals'] as Map<String, dynamic>)['away'] as num).toDouble(),
      confidence: Confidence.parse(json['confidence'] as String?),
      homeMatches: (sample['home_matches'] as num?)?.toInt() ?? 0,
      awayMatches: (sample['away_matches'] as num?)?.toInt() ?? 0,
      topScores: (json['top_scores'] as List<dynamic>)
          .map((e) => ScoreLine.fromJson(e as Map<String, dynamic>))
          .toList(),
      referenceOdds: (json['reference_odds'] as Map<String, dynamic>)
          .map((k, v) => MapEntry(k, (v as num).toDouble())),
      homeContext: TeamContext.fromJson(context['home'] as Map<String, dynamic>),
      awayContext: TeamContext.fromJson(context['away'] as Map<String, dynamic>),
      headToHead: (context['h2h'] as List<dynamic>)
          .map((e) => HeadToHead.fromJson(e as Map<String, dynamic>))
          .toList(),
      explanation: json['explanation'] as String,
      extraMarkets:
          ExtraMarkets.fromJson(json['extra_markets'] as Map<String, dynamic>?),
    );
  }
}

/// Un pariu ales automat de model dintre meciurile afisate.
///
/// Selectia nu urmareste valoarea fata de cota -- aceea a fost masurata si
/// pierde. Urmareste increderea modelului acolo unde piata e de acord cu el.
class Recommendation {
  const Recommendation({
    required this.matchId,
    required this.leagueName,
    required this.date,
    required this.time,
    required this.home,
    required this.away,
    required this.marketLabel,
    required this.probability,
    required this.odds,
    required this.marketProbability,
    required this.band,
    required this.historicalHitRate,
  });

  final String matchId;
  final String leagueName;
  final String date;
  final String time;
  final String home;
  final String away;

  /// "Victorie Arsenal", "Sub 2.5 goluri" etc.
  final String marketLabel;
  final double probability;
  final double odds;
  final double marketProbability;

  /// Banda de probabilitate din care face parte, pentru rata istorica.
  final String band;

  /// Cat de des s-au confirmat istoric selectiile din aceeasi banda.
  final double historicalHitRate;

  factory Recommendation.fromJson(Map<String, dynamic> json) => Recommendation(
        matchId: json['match_id'] as String,
        leagueName: json['league_name'] as String,
        date: json['date'] as String,
        time: (json['time'] as String?) ?? '',
        home: json['home'] as String,
        away: json['away'] as String,
        marketLabel: json['market_label'] as String,
        probability: (json['probability'] as num).toDouble(),
        odds: (json['odds'] as num).toDouble(),
        marketProbability: (json['market_probability'] as num).toDouble(),
        band: (json['band'] as String?) ?? '',
        historicalHitRate: (json['historical_hit_rate'] as num).toDouble(),
      );
}

/// O selecție pe cornere sau cartonașe.
///
/// Se tine separat de celelalte pentru ca nu are cota: pentru pietele astea
/// nicio sursa nu publica cote, deci nu se poate vorbi de randament, doar de
/// cat de des se adeveresc.
class CountPick {
  const CountPick({
    required this.matchId,
    required this.leagueName,
    required this.date,
    required this.time,
    required this.home,
    required this.away,
    required this.marketLabel,
    required this.probability,
    required this.fairOdds,
    required this.historicalHitRate,
  });

  final String matchId;
  final String leagueName;
  final String date;
  final String time;
  final String home;
  final String away;
  final String marketLabel;
  final double probability;

  /// Cota la care pariul ar fi corect: peste ea are sens, sub ea nu.
  final double fairOdds;
  final double historicalHitRate;

  factory CountPick.fromJson(Map<String, dynamic> json) => CountPick(
        matchId: json['match_id'] as String,
        leagueName: json['league_name'] as String,
        date: json['date'] as String,
        time: (json['time'] as String?) ?? '',
        home: json['home'] as String,
        away: json['away'] as String,
        marketLabel: json['market_label'] as String,
        probability: (json['probability'] as num).toDouble(),
        fairOdds: (json['fair_odds'] as num).toDouble(),
        historicalHitRate: (json['historical_hit_rate'] as num).toDouble(),
      );
}

/// O opțiune de pariu la un meci: rezultat, goluri, cornere sau cartonașe.
class MatchPick {
  const MatchPick({
    required this.family,
    required this.market,
    required this.marketLabel,
    required this.probability,
    required this.odds,
    required this.fairOdds,
    required this.historicalHitRate,
    required this.band,
    this.oddsMovement,
  });

  /// Cat s-a miscat cota de cand a aparut selectia: pozitiv = a scazut.
  /// Lipseste la cornere si cartonase, unde n-avem cota de urmarit.
  final double? oddsMovement;

  /// "1x2", "goluri", "cornere", "cartonașe".
  final String family;
  final String market;
  final String marketLabel;
  final double probability;

  /// Cota reala de pe piata. Lipseste la cornere si cartonase, unde nicio
  /// sursa nu publica cote.
  final double? odds;

  /// Cota la care pariul ar fi corect, calculata din probabilitate.
  final double fairOdds;
  final double historicalHitRate;
  final String band;

  bool get hasOdds => odds != null;

  factory MatchPick.fromJson(Map<String, dynamic> json) => MatchPick(
        family: json['family'] as String,
        market: json['market'] as String,
        marketLabel: json['market_label'] as String,
        probability: (json['probability'] as num).toDouble(),
        odds: (json['odds'] as num?)?.toDouble(),
        fairOdds: (json['fair_odds'] as num).toDouble(),
        historicalHitRate: (json['historical_hit_rate'] as num).toDouble(),
        band: (json['band'] as String?) ?? '',
        oddsMovement: (json['odds_movement'] as num?)?.toDouble(),
      );
}

/// Un meci recomandat, cu toate opțiunile lui la un loc.
class RecommendedMatch {
  const RecommendedMatch({
    required this.matchId,
    required this.leagueName,
    required this.date,
    required this.time,
    required this.home,
    required this.away,
    required this.picks,
  });

  final String matchId;
  final String leagueName;
  final String date;
  final String time;
  final String home;
  final String away;
  final List<MatchPick> picks;

  factory RecommendedMatch.fromJson(Map<String, dynamic> json) => RecommendedMatch(
        matchId: json['match_id'] as String,
        leagueName: json['league_name'] as String,
        date: json['date'] as String,
        time: (json['time'] as String?) ?? '',
        home: json['home'] as String,
        away: json['away'] as String,
        picks: ((json['picks'] as List<dynamic>?) ?? [])
            .map((e) => MatchPick.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

/// Un picior al biletului zilei.
class TicketLeg {
  const TicketLeg({
    required this.matchId,
    required this.leagueName,
    required this.date,
    required this.time,
    required this.home,
    required this.away,
    required this.family,
    required this.marketLabel,
    required this.probability,
    required this.odds,
    required this.fairOdds,
    required this.historicalHitRate,
    required this.won,
  });

  final String matchId;
  final String leagueName;
  final String date;
  final String time;
  final String home;
  final String away;
  final String family;
  final String marketLabel;
  final double probability;
  final double? odds;
  final double fairOdds;
  final double historicalHitRate;

  /// Null cat timp meciul nu s-a jucat.
  final bool? won;

  factory TicketLeg.fromJson(Map<String, dynamic> json) => TicketLeg(
        matchId: json['match_id'] as String,
        leagueName: json['league_name'] as String,
        date: json['date'] as String,
        time: (json['time'] as String?) ?? '',
        home: json['home'] as String,
        away: json['away'] as String,
        family: json['family'] as String,
        marketLabel: json['market_label'] as String,
        probability: (json['probability'] as num).toDouble(),
        odds: (json['odds'] as num?)?.toDouble(),
        fairOdds: (json['fair_odds'] as num).toDouble(),
        historicalHitRate: (json['historical_hit_rate'] as num).toDouble(),
        won: json['won'] as bool?,
      );
}

/// Biletul zilei: câteva selecții, din meciuri diferite, într-un singur pariu.
class Ticket {
  const Ticket({
    required this.date,
    required this.legs,
    required this.combinedProbability,
    required this.expectedHitRate,
    required this.combinedOdds,
    required this.oddsEstimated,
    required this.won,
  });

  final String date;
  final List<TicketLeg> legs;

  /// Produsul sanselor date de model.
  final double combinedProbability;

  /// Produsul ratelor masurate istoric pentru fiecare picior.
  final double expectedHitRate;
  final double combinedOdds;

  /// Adevarat cand macar un picior n-are cota reala (cornere, cartonase).
  final bool oddsEstimated;
  final bool? won;

  static Ticket? fromJson(Map<String, dynamic>? json) {
    if (json == null) return null;
    final legs = ((json['legs'] as List<dynamic>?) ?? [])
        .map((e) => TicketLeg.fromJson(e as Map<String, dynamic>))
        .toList();
    if (legs.isEmpty) return null;
    return Ticket(
      date: json['date'] as String,
      legs: legs,
      combinedProbability: (json['combined_probability'] as num).toDouble(),
      expectedHitRate: (json['expected_hit_rate'] as num).toDouble(),
      combinedOdds: (json['combined_odds'] as num).toDouble(),
      oddsEstimated: (json['odds_estimated'] as bool?) ?? false,
      won: json['castigat'] as bool?,
    );
  }
}

/// De ce nu exista bilet azi: cat s-ar putea atinge si de cand se poate.
class TicketUnavailable {
  const TicketUnavailable({
    required this.maxOdds,
    required this.legsAvailable,
    required this.minOdds,
    required this.days,
    required this.nextPossible,
  });

  final double maxOdds;
  final int legsAvailable;
  final double minOdds;
  final int days;

  /// Prima zi in care biletul ar putea include urmatoarea etapa.
  final DateTime? nextPossible;

  static TicketUnavailable? fromJson(Map<String, dynamic>? json) {
    if (json == null) return null;
    final urmatoarea = json['next_possible'] as String?;
    return TicketUnavailable(
      maxOdds: (json['max_odds'] as num).toDouble(),
      legsAvailable: (json['legs_available'] as num).toInt(),
      minOdds: (json['min_odds'] as num).toDouble(),
      days: (json['days'] as num).toInt(),
      nextPossible: urmatoarea == null ? null : DateTime.parse(urmatoarea),
    );
  }
}

/// Cate bilete ale zilei au iesit pana acum.
class TicketRecord {
  const TicketRecord({
    required this.total,
    required this.resolved,
    required this.won,
    required this.expected,
  });

  final int total;
  final int resolved;
  final int won;

  /// Cat ar fi trebuit sa iasa, in medie, dupa ratele masurate.
  final double? expected;

  static TicketRecord? fromJson(Map<String, dynamic>? json) {
    if (json == null) return null;
    return TicketRecord(
      total: (json['total'] as num?)?.toInt() ?? 0,
      resolved: (json['resolved'] as num?)?.toInt() ?? 0,
      won: (json['won'] as num?)?.toInt() ?? 0,
      expected: (json['expected'] as num?)?.toDouble(),
    );
  }
}

/// Bilantul selectiilor fara cota, tinut separat de cel cu randament.
class CountsRecord {
  const CountsRecord({
    required this.total,
    required this.resolved,
    required this.pending,
    required this.hits,
    required this.hitRate,
    required this.expected,
  });

  final int total;
  final int resolved;
  final int pending;
  final int hits;
  final double? hitRate;
  final double expected;

  static CountsRecord? fromJson(Map<String, dynamic>? json) {
    if (json == null) return null;
    final total = (json['total'] as num?)?.toInt() ?? 0;
    if (total == 0) return null;
    return CountsRecord(
      total: total,
      resolved: (json['resolved'] as num?)?.toInt() ?? 0,
      pending: (json['pending'] as num?)?.toInt() ?? 0,
      hits: (json['hits'] as num?)?.toInt() ?? 0,
      hitRate: (json['hit_rate'] as num?)?.toDouble(),
      expected: (json['expected'] as num?)?.toDouble() ?? 0.65,
    );
  }
}

/// Cum s-a descurcat o banda de probabilitate in realitate, fata de backtest.
class BandRecord {
  const BandRecord({
    required this.band,
    required this.count,
    required this.hits,
    required this.rate,
    required this.expected,
  });

  final String band;
  final int count;
  final int hits;
  final double rate;

  /// Rata masurata in backtest pentru aceeasi banda.
  final double expected;

  factory BandRecord.fromJson(Map<String, dynamic> json) => BandRecord(
        band: json['band'] as String,
        count: (json['n'] as num).toInt(),
        hits: (json['hits'] as num).toInt(),
        rate: (json['rate'] as num).toDouble(),
        expected: (json['expected'] as num).toDouble(),
      );
}

/// O selectie notata, cu rezultatul ei daca meciul s-a jucat.
///
/// Ecranul principal arata doar trei zile, deci meciurile trecute dispar de
/// acolo. Lista asta e singurul loc in care raman vizibile.
class SelectionRecord {
  const SelectionRecord({
    required this.matchId,
    required this.date,
    required this.leagueName,
    required this.home,
    required this.away,
    required this.marketLabel,
    required this.probability,
    required this.odds,
    required this.band,
    required this.won,
    required this.score,
  });

  final String matchId;
  final DateTime date;
  final String leagueName;
  final String home;
  final String away;
  final String marketLabel;
  final double probability;

  /// Lipseste la cornere si cartonase: pentru ele nu exista cote nicaieri.
  final double? odds;
  final String band;

  /// Null cat timp meciul nu s-a jucat sau scorul inca nu a ajuns in date.
  final bool? won;
  final String? score;

  bool get isPending => won == null;

  /// Castig sau pierdere la o miza de o unitate, la cota din momentul notarii.
  /// Null si cand pariul n-a avut cota, nu doar cand meciul nu s-a jucat.
  double? get profitUnits =>
      (won == null || odds == null) ? null : (won! ? odds! - 1 : -1.0);

  factory SelectionRecord.fromJson(Map<String, dynamic> json) => SelectionRecord(
        matchId: json['match_id'] as String,
        date: DateTime.parse(json['date'] as String),
        leagueName: json['league_name'] as String,
        home: json['home'] as String,
        away: json['away'] as String,
        marketLabel: json['market_label'] as String,
        probability: (json['probability'] as num).toDouble(),
        // Selectiile pe cornere si cartonase n-au cota: pentru pietele alea
        // nicio sursa nu publica una.
        odds: (json['odds'] as num?)?.toDouble(),
        band: (json['band'] as String?) ?? '',
        won: json['won'] as bool?,
        score: json['score'] as String?,
      );
}

/// Bilantul propriilor selectii, verificate dupa ce meciurile s-au jucat.
///
/// Backtestul e o promisiune despre trecut; asta e o dovada despre prezent.
class TrackRecord {
  const TrackRecord({
    required this.total,
    required this.resolved,
    required this.pending,
    required this.hits,
    required this.hitRate,
    required this.profitUnits,
    required this.roi,
    required this.bands,
    required this.since,
    required this.selections,
    required this.counts,
  });

  final int total;
  final int resolved;
  final int pending;
  final int hits;

  /// Null cat timp nu s-a terminat niciun meci.
  final double? hitRate;
  final double? profitUnits;
  final double? roi;
  final List<BandRecord> bands;
  final String? since;

  /// Selectiile notate, cele mai noi intai. Goala in fisierele generate
  /// inainte de aparitia ecranului de istoric.
  final List<SelectionRecord> selections;

  /// Bilantul separat al selectiilor pe cornere si cartonase.
  final CountsRecord? counts;

  bool get hasResults => resolved > 0 && hitRate != null;

  factory TrackRecord.fromJson(Map<String, dynamic> json) => TrackRecord(
        total: (json['total'] as num).toInt(),
        resolved: (json['resolved'] as num).toInt(),
        pending: (json['pending'] as num).toInt(),
        hits: (json['hits'] as num).toInt(),
        hitRate: (json['hit_rate'] as num?)?.toDouble(),
        profitUnits: (json['profit_units'] as num?)?.toDouble(),
        roi: (json['roi'] as num?)?.toDouble(),
        bands: ((json['by_band'] as List<dynamic>?) ?? [])
            .map((e) => BandRecord.fromJson(e as Map<String, dynamic>))
            .toList(),
        since: json['since'] as String?,
        selections: ((json['selections'] as List<dynamic>?) ?? [])
            .map((e) => SelectionRecord.fromJson(e as Map<String, dynamic>))
            .toList(),
        counts: CountsRecord.fromJson(json['counts'] as Map<String, dynamic>?),
      );
}

/// Rezultatele backtest-ului, afisate in aplicatie asa cum sunt.
class BacktestInfo {
  const BacktestInfo({
    required this.matchesTested,
    required this.period,
    required this.logLoss,
    required this.accuracy,
    required this.ece,
    required this.marketLogLoss,
    required this.beatsMarket,
    required this.note,
  });

  final int matchesTested;
  final String period;
  final double logLoss;
  final double accuracy;
  final double ece;
  final double marketLogLoss;
  final bool beatsMarket;
  final String note;

  factory BacktestInfo.fromJson(Map<String, dynamic> json) => BacktestInfo(
        matchesTested: (json['matches_tested'] as num).toInt(),
        period: json['period'] as String,
        logLoss: (json['log_loss'] as num).toDouble(),
        accuracy: (json['accuracy'] as num).toDouble(),
        ece: (json['ece'] as num).toDouble(),
        marketLogLoss: (json['market_log_loss'] as num).toDouble(),
        beatsMarket: json['beats_market'] as bool,
        note: json['note'] as String,
      );
}

/// Cand se reiau meciurile, in pauzele competitionale.
///
/// Exista ca sa se poata deosebi o pauza de o defectiune: fara ea, o listă
/// goala si o lista inghetata arata la fel.
class NextRound {
  const NextRound({required this.date, required this.competitions});

  final DateTime date;

  /// Cine joaca in prima zi: de obicei una-doua competitii.
  final List<String> competitions;

  static NextRound? fromJson(Map<String, dynamic>? json) {
    final data = json?['date'] as String?;
    if (data == null) return null;
    return NextRound(
      date: DateTime.parse(data),
      competitions: ((json!['competitions'] as List<dynamic>?) ?? [])
          .map((e) => e as String)
          .toList(),
    );
  }
}

class PredictionBundle {
  const PredictionBundle({
    required this.generatedAt,
    required this.modelName,
    required this.backtest,
    required this.matches,
    required this.recommendations,
    required this.trackRecord,
    required this.nextRound,
    required this.countPicks,
    required this.recommendedMatches,
    required this.ticket,
    required this.ticketRecord,
    required this.ticketUnavailable,
  });

  final DateTime generatedAt;
  final String modelName;
  final BacktestInfo backtest;
  final List<MatchPrediction> matches;
  final List<Recommendation> recommendations;

  /// Lipseste pana la prima rulare care noteaza selectii.
  final TrackRecord? trackRecord;

  /// Prezent doar cand nu sunt meciuri in fereastra afisata.
  final NextRound? nextRound;

  /// Selectiile pe cornere si cartonase, fara cota.
  final List<CountPick> countPicks;

  /// Meciurile recomandate, fiecare cu opțiunile lui pe toate piețele.
  final List<RecommendedMatch> recommendedMatches;

  /// Biletul zilei; lipseste cand nu sunt destule selectii pentru unul.
  final Ticket? ticket;
  final TicketRecord? ticketRecord;

  /// Prezent cand azi nu iese niciun bilet care sa respecte regulile.
  final TicketUnavailable? ticketUnavailable;

  factory PredictionBundle.fromJson(Map<String, dynamic> json) {
    final model = json['model'] as Map<String, dynamic>;
    return PredictionBundle(
      generatedAt: DateTime.parse(json['generated_at'] as String).toLocal(),
      modelName: model['name'] as String,
      backtest: BacktestInfo.fromJson(model['backtest'] as Map<String, dynamic>),
      matches: (json['matches'] as List<dynamic>)
          .map((e) => MatchPrediction.fromJson(e as Map<String, dynamic>))
          .toList(),
      // Lipseste in fisierele generate inainte de aparitia sectiunii.
      recommendations: ((json['recommendations'] as List<dynamic>?) ?? [])
          .map((e) => Recommendation.fromJson(e as Map<String, dynamic>))
          .toList(),
      trackRecord: json['track_record'] == null
          ? null
          : TrackRecord.fromJson(json['track_record'] as Map<String, dynamic>),
      nextRound: NextRound.fromJson(json['next_round'] as Map<String, dynamic>?),
      countPicks: ((json['count_picks'] as List<dynamic>?) ?? [])
          .map((e) => CountPick.fromJson(e as Map<String, dynamic>))
          .toList(),
      recommendedMatches: ((json['recommended_matches'] as List<dynamic>?) ?? [])
          .map((e) => RecommendedMatch.fromJson(e as Map<String, dynamic>))
          .toList(),
      ticket: Ticket.fromJson(json['ticket_of_the_day'] as Map<String, dynamic>?),
      ticketRecord:
          TicketRecord.fromJson(json['ticket_record'] as Map<String, dynamic>?),
      ticketUnavailable: TicketUnavailable.fromJson(
          json['ticket_unavailable'] as Map<String, dynamic>?),
    );
  }
}
