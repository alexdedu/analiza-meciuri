/// Configurarea sursei de date.
///
/// Daca lasi `predictionsUrl` gol, aplicatia foloseste doar fisierul inclus in
/// APK — adica vezi meciurile care existau in momentul construirii aplicatiei.
///
/// Daca pui aici un URL public catre predictions.json (de exemplu fisierul din
/// repo-ul tau de GitHub), aplicatia il descarca la fiecare pornire si la fiecare
/// tragere in jos a listei. Atunci nu mai trebuie reinstalata niciodata: workflow-ul
/// zilnic rescrie fisierul, iar telefonul il ia singur.
///
/// Forma URL-ului pentru un repo GitHub public:
///   https://raw.githubusercontent.com/<utilizator>/<repo>/main/app/assets/predictions.json
const String predictionsUrl =
    'https://raw.githubusercontent.com/alexdedu/analiza-meciuri/main/app/assets/predictions.json';

/// Cat asteptam dupa server inainte sa ne intoarcem la datele locale.
const Duration remoteTimeout = Duration(seconds: 8);
