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
  final double odds;
  final String band;

  /// Null cat timp meciul nu s-a jucat sau scorul inca nu a ajuns in date.
  final bool? won;
  final String? score;

  bool get isPending => won == null;

  /// Castig sau pierdere la o miza de o unitate, la cota din momentul notarii.
  double? get profitUnits => won == null ? null : (won! ? odds - 1 : -1.0);

  factory SelectionRecord.fromJson(Map<String, dynamic> json) => SelectionRecord(
        matchId: json['match_id'] as String,
        date: DateTime.parse(json['date'] as String),
        leagueName: json['league_name'] as String,
        home: json['home'] as String,
        away: json['away'] as String,
        marketLabel: json['market_label'] as String,
        probability: (json['probability'] as num).toDouble(),
        odds: (json['odds'] as num).toDouble(),
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

class PredictionBundle {
  const PredictionBundle({
    required this.generatedAt,
    required this.modelName,
    required this.backtest,
    required this.matches,
    required this.recommendations,
    required this.trackRecord,
  });

  final DateTime generatedAt;
  final String modelName;
  final BacktestInfo backtest;
  final List<MatchPrediction> matches;
  final List<Recommendation> recommendations;

  /// Lipseste pana la prima rulare care noteaza selectii.
  final TrackRecord? trackRecord;

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
    );
  }
}
