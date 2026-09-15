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
  });

  final DateTime generatedAt;
  final String modelName;
  final BacktestInfo backtest;
  final List<MatchPrediction> matches;

  factory PredictionBundle.fromJson(Map<String, dynamic> json) {
    final model = json['model'] as Map<String, dynamic>;
    return PredictionBundle(
      generatedAt: DateTime.parse(json['generated_at'] as String).toLocal(),
      modelName: model['name'] as String,
      backtest: BacktestInfo.fromJson(model['backtest'] as Map<String, dynamic>),
      matches: (json['matches'] as List<dynamic>)
          .map((e) => MatchPrediction.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}
