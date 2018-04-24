$( document ).ready(function(){

    /* 
    set crsf protection
    */
    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = jQuery.trim(cookies[i]);
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

var csrftoken = getCookie('csrftoken');
    /* if lang is not set in uri,
     get the browser language
     and set lang parmeter
     default to en 
    */
    var lang = get_param('lang');
    if ( ! lang ){
        var pref_lang = get_browser_language();
        switch(pref_lang){
            case 'ar':
                setDefaultLang('ar');
                break;
            case 'zh':
                setDefaultLang('zh');
                break;
            case 'en':
                setDefaultLang('en');
                break;
            case 'fr':
                setDefaultLang('fr');
                break;
            case 'ru':
                setDefaultLang('ru');
                break;
            case 'es':
                setDefaultLang('es');
                break;
            default:
                setDefaultLang('en');
                break;
            }
        }

    /* autocomplete functionality
     want to grab characters typed into search form
     and pass them via ajax to the search method
     if search method returns results, add
     to select area under form
    */
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

    /* when click on a language
        translate whole page
    */
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

    // show API dialog
    $("#getNode").on("click", function(e){
        $("#show-dl-options").modal("show");
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

function setDefaultLang(lang){
    // var href = document.getElementById(lang);
    // console.log(href);
    // href.style.fontWeight = 'bold';
    var searchParams = new URLSearchParams(window.location.search);
    searchParams.set("lang", lang);
    window.location.search = searchParams.toString();
}