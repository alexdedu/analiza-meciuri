import 'package:flutter/material.dart';

import 'search_card.dart';
import 'theme.dart';
import 'widgets.dart';

/// Cautare pentru orice meci, inclusiv cele pe care aplicatia nu le acopera:
/// Champions League, Europa League, amicale, alte campionate.
class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key});

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final _home = TextEditingController();
  final _away = TextEditingController();

  @override
  void dispose() {
    _home.dispose();
    _away.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Caută un meci')),
      body: ListView(
        padding: EdgeInsets.fromLTRB(
            16, 8, 16, 32 + MediaQuery.paddingOf(context).bottom),
        children: [
          SectionCard(
            title: 'Echipele',
            subtitle: 'Scrie numele lor, cum le știi. Nu trebuie să fie exacte.',
            child: Column(
              children: [
                TextField(
                  controller: _home,
                  textInputAction: TextInputAction.next,
                  decoration: const InputDecoration(hintText: 'Gazdă — ex. AC Milan'),
                  onChanged: (_) => setState(() {}),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: _away,
                  textInputAction: TextInputAction.search,
                  decoration: const InputDecoration(hintText: 'Oaspete — ex. Benfica'),
                  onChanged: (_) => setState(() {}),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          SearchCard(
            home: _home.text,
            away: _away.text,
            title: 'Deschide în browser',
            subtitle: 'Căutarea se face în browserul telefonului. '
                'Aplicația nu citește și nu preia nimic de acolo.',
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('De ce nu apar aici meciurile europene',
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 10),
                  const Text(
                    'Champions League și Europa League nu există în nicio sursă de date '
                    'gratuită. Chiar dacă ar exista, modelul compară echipe doar în '
                    'interiorul aceluiași campionat: forța lor e măsurată față de restul '
                    'ligii, nu pe o scară comună. Un Milan – Benfica i-ar ieși pe ghicite, '
                    'așa că prefer să nu-ți arate un procent inventat.',
                    style: TextStyle(fontSize: 12.5, height: 1.5, color: AppColors.textSecondary),
                  ),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppColors.warning.withValues(alpha: 0.10),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Text(
                      'Despre ponturile găsite pe alte site-uri: aproape niciunul nu publică '
                      'un istoric verificabil al propriilor predicții. Backtest-ul acestei '
                      'aplicații arată că nici un model statistic serios nu bate cotele de '
                      'închidere — deci tratează-le ca opinii, nu ca informație.',
                      style: TextStyle(
                          fontSize: 11.5, height: 1.4, color: AppColors.textSecondary),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
