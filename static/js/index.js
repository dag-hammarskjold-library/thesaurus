$( document ).ready(function(){
    function get_lang(){
        var url_string = window.location.href;
        var url = new URL(url_string);
        var lang = url.searchParams.get("lang");
        if(lang){
            return lang;
        } else {
            return 'en';
        }
    }

    // $("#autocomplete").on("focus", function(e){
    //     console.log(e);
    //     var lang = get_lang();
    //     document.getElementById("lang-input").value = lang;
    // });

    var xhr;
    var lang = get_lang();
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
            lang = get_lang();
            console.log(ui);
            window.location = "/term?lang=" + lang + "&base_uri=" + ui.item.base_uri + "&uri_anchor=" + ui.item.uri_anchor;
        }
    });

    $(".lang").on("click", function(e){
        e.preventDefault();
        var currentURL = window.location.href;
        var lang = get_lang();
        var prefLang = this.id;
        console.log(prefLang);
        var searchParams = new URLSearchParams(window.location.search);
        searchParams.set("lang", prefLang);
        window.location.search = searchParams.toString();
        
    });
});