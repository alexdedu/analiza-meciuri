/// Construieste adrese de cautare pentru un meci.
///
/// Totul trece prin Google, chiar si cautarile "de statistici". Motivul e
/// practic: adresele interne ale site-urilor de sport se schimba des, iar unele
/// blocheaza accesul din afara browserului. Google ramane stabil, iar cuvintele
/// din interogare duc oricum la sursa potrivita.
library;

enum SearchKind {
  /// Ce s-a scris despre meci, in general.
  general,

  /// Statistici, formatii probabile, intalniri directe.
  statistici,

  /// Ponturile publicate de alte site-uri.
  ponturi;

  String get label => switch (this) {
        SearchKind.general => 'Caută meciul',
        SearchKind.statistici => 'Statistici și formații',
        SearchKind.ponturi => 'Ce pronosticuri dau alții',
      };

  String get hint => switch (this) {
        SearchKind.general => 'Știri și context despre meci',
        SearchKind.statistici => 'Cifre verificabile: forma, xG, întâlniri directe',
        SearchKind.ponturi => 'Opinii publicate, fără istoric verificabil',
      };
}

/// Cuvintele adaugate la numele echipelor, pentru fiecare tip de cautare.
const _extraTerms = {
  SearchKind.general: '',
  SearchKind.statistici: 'statistici sofascore fbref',
  SearchKind.ponturi: 'ponturi pronostic',
};

/// `AC Milan` + `Benfica` -> adresa de cautare Google.
///
/// Numele echipelor vin fie din predictii, fie scrise de mana, deci pot contine
/// spatii in plus, diacritice sau caractere care strica adresa. Uri le codeaza.
Uri buildSearchUrl(String home, String away, SearchKind kind) {
  final gazda = home.trim();
  final oaspete = away.trim();

  final parts = <String>[
    if (gazda.isNotEmpty) gazda,
    if (gazda.isNotEmpty && oaspete.isNotEmpty) 'vs',
    if (oaspete.isNotEmpty) oaspete,
    if (_extraTerms[kind]!.isNotEmpty) _extraTerms[kind]!,
  ];

  return Uri.https('www.google.com', '/search', {'q': parts.join(' ')});
}

/// Avem destule date pentru o cautare? (macar o echipa scrisa)
bool canSearch(String home, String away) =>
    home.trim().isNotEmpty || away.trim().isNotEmpty;
