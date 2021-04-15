import $ from 'jquery'
import 'bootstrap'

$(document).on('click', '.support-file', function () {
    $.ajax({
        dataType: "json",
        url: '/record/resource/' + $(this).attr('data-file-id'),
        processData: false,
        cache: true,
        success: function (data) {


            $("#file-description").html(data.description);
            $(".code-viewer-title").text(data.type.toUpperCase() + " File");
            var image_file_types = ["png", "jpeg", "jpg", "tiff", "gif"];

            if (image_file_types.indexOf(data.type.toLowerCase()) != -1) {
                $("#code").html('<img src="' + data.location + '" width="100%"></img>');
            } else if (data.type == 'root') {
                $("#codeDialogLabel").html('ROOT');
                $("#code").html('We can\'t display ROOT files at present. But you can download it!');
            } else {
                $("#code").html('<textarea id="code-contents"></textarea>');
                $("#code-contents").val(data.file_contents);
            }

            $("#file_download_btn").attr('href', data.location);

            $('#codeDialog').modal('show');
            $("#code").focus();
        },
        error: function (error) {
            $("#code").html('We can\'t display this type of file at present. But you can download it!');
            $('#codeDialog').modal('show');
        }
    });
});
