import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:football_predictor/models.dart';

/// Testam pe fisierul real generat de research/predict.py, nu pe unul inventat.
/// Daca pipeline-ul schimba structura, testul pica aici, nu in aplicatie.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late PredictionBundle bundle;

  setUpAll(() async {
    final raw = await rootBundle.loadString('assets/predictions.json');
    bundle = PredictionBundle.fromJson(jsonDecode(raw) as Map<String, dynamic>);
  });

  test('fisierul de predictii se parseaza complet', () {
    expect(bundle.matches, isNotEmpty);
    expect(bundle.modelName, isNotEmpty);
  });

  test('probabilitatile 1X2 insumeaza 1', () {
    for (final m in bundle.matches) {
      final total = m.p('p_home') + m.p('p_draw') + m.p('p_away');
      expect(total, closeTo(1.0, 0.01), reason: 'la meciul ${m.id}');
    }
  });

  test('pietele complementare insumeaza 1', () {
    for (final m in bundle.matches) {
      expect(m.p('p_over25') + m.p('p_under25'), closeTo(1.0, 0.01));
      expect(m.p('p_btts') + m.p('p_no_btts'), closeTo(1.0, 0.01));
    }
  });

  test('fiecare probabilitate e intre 0 si 1', () {
    for (final m in bundle.matches) {
      for (final entry in m.probabilities.entries) {
        expect(entry.value, inInclusiveRange(0.0, 1.0),
            reason: '${m.id} / ${entry.key}');
      }
    }
  });

  test('golurile asteptate sunt pozitive si plauzibile', () {
    for (final m in bundle.matches) {
      expect(m.expectedGoalsHome, greaterThan(0));
      expect(m.expectedGoalsAway, greaterThan(0));
      expect(m.expectedGoalsHome + m.expectedGoalsAway, lessThan(10));
    }
  });

  test('echipele cu putine meciuri sunt marcate cu incredere scazuta', () {
    // Pragurile difera intre cluburi si nationale, si asta e intentionat: un
    // club joaca ~38 de meciuri pe an, o nationala ~10. Acelasi prag ar face ca
    // orice meci de nationala sa para nesigur.
    for (final m in bundle.matches) {
      final smallest = m.homeMatches < m.awayMatches ? m.homeMatches : m.awayMatches;
      final nationala = m.id.startsWith('NAT');
      final pragJos = nationala ? 12 : 15;
      final pragSus = nationala ? 25 : 40;

      if (smallest < pragJos) {
        expect(m.confidence, Confidence.scazuta, reason: m.id);
      } else if (smallest >= pragSus) {
        expect(m.confidence, Confidence.ridicata, reason: m.id);
      }
    }
  });

  test('backtestul raportat nu pretinde ca bate piata', () {
    expect(bundle.backtest.beatsMarket, isFalse);
    expect(bundle.backtest.marketLogLoss, lessThan(bundle.backtest.logLoss));
  });

  test('fiecare meci are explicatie si scoruri probabile', () {
    for (final m in bundle.matches) {
      expect(m.explanation, isNotEmpty);
      expect(m.topScores, hasLength(5));
      expect(m.topScores.first.probability,
          greaterThanOrEqualTo(m.topScores.last.probability));
    }
  });
}
