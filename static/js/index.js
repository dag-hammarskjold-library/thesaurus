$( document ).ready(function(){

    var pref_lang = get_browser_language();
    switch(pref_lang){
        case 'ar':
            highlightLang('ar');
            break;
        case 'zh':
            highlightLang('zh');
            break;
        case 'en':
            highlightLang('en');
            break;
        case 'fr':
            highlightLang('fr');
            break;
        case 'ru':
            highlightLang('ru');
            break;
        case 'es':
            highlightLang('es');
            break;
        default:
            highlightLang('en');
            break;
        }

    var xhr;
    var lang = get_param('lang');
    xhr = $('#autocomplete').autocomplete({
        minLength:2,   
        delay:500,
        source: function( request, response ){
            xhr = $.ajax({
                url: "/autocomplete?lang=" + lang + "&q=" + request.term,
                dataType: "json",
                cache: false,
                success: function(data) {
                    console.log(data);
                    response($.map(data, function(item) {
                        return {
                            label: item.pref_label,
                            base_uri: item.base_uri,
                            uri_anchor: item.uri_anchor
                        };
                    }));
                }
            });
        }, select: function(event, ui) {
            lang = get_param('lang');
            console.log(ui);
            window.location = "/term?lang=" + lang + "&base_uri=" + ui.item.base_uri + "&uri_anchor=" + ui.item.uri_anchor;
        }
    });

    $(".lang").on("click", function(e){
        e.preventDefault();
        var currentURL = window.location.href;
        var lang = get_param('lang');
        var prefLang = this.id;
        console.log(prefLang);
        var searchParams = new URLSearchParams(window.location.search);
        searchParams.set("lang", prefLang);
        window.location.search = searchParams.toString();
    }); 
});

function get_param(param){
    var url_string = window.location.href;
    var url = new URL(url_string);
    var myParam = url.searchParams.get(param);
    return myParam;
}

function get_browser_language(){
    var lang_locale = navigator.language;
    var parts = lang_locale.split('-');
    return parts[0];
}

function highlightLang(lang){
    var href = document.getElementById(lang);
    console.log(href);
    href.style.fontWeight = 'bold';
}