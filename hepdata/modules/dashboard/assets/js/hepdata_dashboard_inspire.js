import $ from 'jquery'
import inspire_ds from './inspire.js'

$(document).on('click', '#inspire-retrieve-button', function () {
//            $("#inspire_retrieve_button_container").addClass("hidden");
    $("#inspire-result").removeClass("well well-sm");
    $("#inspire-result").html('');
    $("#inspire-retrieve-progress").removeClass("hidden");

    var inspire_id = $("#inspire-id").val();

    inspire_ds.get_inspire_data(inspire_id, inspire_ds.render_inspire_data);

});

$(document).on('click', '#inspire-add-button', function () {

    $("#inspire-result").addClass("hidden");
    $("#inspire-add-progress").removeClass("hidden");

    $.ajax({
        dataType: "json",
        method: 'POST',
        url: '/record/attach_information/' + $(this).attr('data-recid'),
        data: {'inspire_id': window.inspire_id},
        success: function (data) {
            if (data.status != 'success') {
                alert("Error (" + data.status + ")! " + data.message)
            }
            setTimeout(function () {
                window.location = "/dashboard";
            }, 1000);
        }
    });
});

$(document).on("keyup", "#inspire-id", function () {
    $("#inspire-retrieve-button").toggleClass("disabled", $(this).val() == '')
})
