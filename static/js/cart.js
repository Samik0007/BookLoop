var updateBtns = document.getElementsByClassName('update-cart')

for(var i = 0; i < updateBtns.length; i++){
    updateBtns[i].addEventListener('click', function(){
        var productId = this.dataset.product
        var action = this.dataset.action
        console.log('productId:', productId, 'Action:', action)
        console.log('USER:', user)
        if(user == 'AnonymousUser'){
            alert('Please login first to add items to cart!');
            window.location.href = '/login/';
        }else{
            updateUserOrder(productId, action)
        }
    })
}

function updateUserOrder(productId, action){
    console.log('User is authenticated, sending data...')
    
    var url = '/update_item/'
    
    fetch(url, {
        method:'POST',
        headers:{
            'Content-Type':'application/json',
            'X-CSRFToken': csrftoken,
        },
        body:JSON.stringify({'productId':productId, 'action':action})
    })
    .then((response) => {
        return response.json();
    })
    .then((data) => {
        if (data.error === 'out_of_stock') {
            alertify ? alertify.error('This book is out of stock.') : alert('This book is out of stock.')
            return
        }
        location.reload()
    });
}
