import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'models.dart';
import 'repository.dart';
import 'theme.dart';
import 'widgets.dart';

/// Introduci manual cota de la casa ta de pariuri; aplicatia o compara cu
/// "cota corecta" a modelului (1 / probabilitate).
///
/// Nu foloseste niciun API de cote -- de aceea aplicatia e complet gratuita.
class ValueCalculator extends StatefulWidget {
  const ValueCalculator({super.key, required this.match, required this.store});

  final MatchPrediction match;
  final OddsStore store;

  @override
  State<ValueCalculator> createState() => _ValueCalculatorState();
}

class _MarketSpec {
  const _MarketSpec(this.key, this.label, this.probKey);
  final String key;
  final String label;
  final String probKey;
}

class _ValueCalculatorState extends State<ValueCalculator> {
  late final List<_MarketSpec> _markets = [
    _MarketSpec('home', '1 — ${widget.match.home}', 'p_home'),
    const _MarketSpec('draw', 'X — Egal', 'p_draw'),
    _MarketSpec('away', '2 — ${widget.match.away}', 'p_away'),
    const _MarketSpec('over25', 'Peste 2.5 goluri', 'p_over25'),
    const _MarketSpec('under25', 'Sub 2.5 goluri', 'p_under25'),
    const _MarketSpec('btts', 'Ambele inscriu — Da', 'p_btts'),
    const _MarketSpec('nobtts', 'Ambele inscriu — Nu', 'p_no_btts'),
  ];

  final Map<String, TextEditingController> _controllers = {};

  @override
  void initState() {
    super.initState();
    for (final m in _markets) {
      final saved = widget.store.read(widget.match.id, m.key);
      _controllers[m.key] = TextEditingController(
        text: saved == null ? '' : saved.toStringAsFixed(2),
      );
    }
  }

  @override
  void dispose() {
    for (final c in _controllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  void _onChanged(String marketKey, String raw) {
    final value = double.tryParse(raw.replaceAll(',', '.'));
    widget.store.write(widget.match.id, marketKey, value);
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: 'Calculator de valoare',
      subtitle: 'Introdu cota de la casa ta. Compar cu cota corecta a modelului.',
      child: Column(
        children: [
          for (final market in _markets) _buildRow(market),
          const SizedBox(height: 10),
          const Text(
            'Reper: in backtest, selectia dupa acest avantaj a dat −3.7% pe 43.101 de pariuri.',
            style: TextStyle(fontSize: 11, color: AppColors.textSecondary, height: 1.3),
          ),
        ],
      ),
    );
  }

  Widget _buildRow(_MarketSpec market) {
    final probability = widget.match.p(market.probKey);
    final fairOdds = probability > 0 ? 1 / probability : double.infinity;
    final entered = double.tryParse(_controllers[market.key]!.text.replaceAll(',', '.'));
    final hasOdds = entered != null && entered > 1.0;
    final edge = hasOdds ? probability * entered - 1 : null;

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          Expanded(
            flex: 5,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(market.label,
                    style: const TextStyle(fontSize: 13, color: AppColors.textPrimary),
                    overflow: TextOverflow.ellipsis),
                const SizedBox(height: 2),
                Text(
                  'model ${(probability * 100).toStringAsFixed(1)}%  ·  corect '
                  '${fairOdds.isFinite ? fairOdds.toStringAsFixed(2) : "—"}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 11, color: AppColors.textSecondary),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          SizedBox(
            width: 74,
            child: TextField(
              controller: _controllers[market.key],
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.,]'))],
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
              decoration: const InputDecoration(hintText: 'cota'),
              onChanged: (v) => _onChanged(market.key, v),
            ),
          ),
          SizedBox(
            width: 68,
            child: edge == null
                ? const Text('—',
                    textAlign: TextAlign.right,
                    style: TextStyle(fontSize: 13, color: AppColors.textSecondary))
                : Text(
                    '${edge >= 0 ? '+' : ''}${(edge * 100).toStringAsFixed(1)}%',
                    textAlign: TextAlign.right,
                    style: TextStyle(
                      fontSize: 13.5,
                      fontWeight: FontWeight.w700,
                      color: edge >= 0.05
                          ? AppColors.positive
                          : (edge >= 0 ? AppColors.textPrimary : AppColors.negative),
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}
