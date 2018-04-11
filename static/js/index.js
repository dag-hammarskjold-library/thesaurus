$( document ).ready(function(){
    $('#q').autocomplete({
        minLength:2,   
        delay:500,
        source: function(request, response) {
            var requestUrl = "/autocomplete"
            $.ajax({
                url: requestUrl,
                type: "GET",
                data: {"q": request.term},
                async: false
            }).done(function(msg) {
                console.log(msg);
            });
        }
    });
});